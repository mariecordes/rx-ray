from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.dossier.models import (
    ResolutionCandidate,
    RxNormConcept,
    RxNormEdge,
    RxNormNeighborhood,
)


DEFAULT_RELATIONS = {
    "has_ingredient",
    "has_ingredients",
    "has_precise_ingredient",
    "has_tradename",
    "has_dose_form",
    "has_doseformgroup",
    "has_form",
    "has_part",
    "contains",
    "consists_of",
    "constitutes",
    "ingredient_of",
    "ingredients_of",
    "precise_ingredient_of",
    "tradename_of",
    "dose_form_of",
    "form_of",
    "part_of",
}

TTY_PRIORITY = {
    "IN": 0,
    "PIN": 1,
    "MIN": 2,
    "BN": 3,
    "SCD": 4,
    "SBD": 5,
    "SCDF": 6,
    "SBDF": 7,
    "SCDC": 8,
    "SBDC": 9,
}


class RxNormParquetStore:
    """Read-only RxNorm resolver and graph retriever backed by parquet files."""

    def __init__(
        self,
        rxnconso_path: str | Path = "data/01_raw/rxnconso_raw.parquet",
        rxnrel_path: str | Path = "data/01_raw/rxnrel_raw.parquet",
    ) -> None:
        self.rxnconso_path = Path(rxnconso_path)
        self.rxnrel_path = Path(rxnrel_path)
        self._rxnconso: pd.DataFrame | None = None
        self._rxnrel: pd.DataFrame | None = None
        self._preferred: pd.DataFrame | None = None

    @property
    def rxnconso(self) -> pd.DataFrame:
        if self._rxnconso is None:
            self._rxnconso = pd.read_parquet(self.rxnconso_path)
            self._rxnconso["STR_NORM"] = self._rxnconso["STR"].fillna("").str.casefold()
        return self._rxnconso

    @property
    def rxnrel(self) -> pd.DataFrame:
        if self._rxnrel is None:
            self._rxnrel = pd.read_parquet(self.rxnrel_path)
        return self._rxnrel

    @property
    def preferred_names(self) -> pd.DataFrame:
        if self._preferred is None:
            df = self.rxnconso.copy()
            df = df[(df["LAT"] == "ENG") & (df["STR"].notna())]
            df = df.assign(
                sab_rank=(df["SAB"] != "RXNORM").astype(int),
                suppress_rank=(df["SUPPRESS"] != "N").astype(int),
                cvf_rank=(df["CVF"] != "4096").astype(int),
                tty_rank=df["TTY"].map(TTY_PRIORITY).fillna(99).astype(int),
                name_len=df["STR"].str.len(),
            )
            df = df.sort_values(
                [
                    "RXCUI",
                    "sab_rank",
                    "suppress_rank",
                    "cvf_rank",
                    "tty_rank",
                    "name_len",
                    "STR",
                ]
            )
            self._preferred = df.drop_duplicates("RXCUI", keep="first")
        return self._preferred

    def resolve(self, drug_name: str, limit: int = 5) -> list[ResolutionCandidate]:
        """Resolve a user drug name to ranked RxNorm concepts."""

        query = drug_name.strip().casefold()
        if not query:
            return []

        df = self.rxnconso
        exact = df[df["STR_NORM"] == query].copy()
        exact["match_type"] = "exact"
        exact["score"] = 100.0

        startswith = df[
            (df["STR_NORM"].str.startswith(query)) & (df["STR_NORM"] != query)
        ].copy()
        startswith["match_type"] = "prefix"
        startswith["score"] = 80.0

        contains = df[
            (df["STR_NORM"].str.contains(query, regex=False))
            & (~df["STR_NORM"].str.startswith(query))
        ].copy()
        contains["match_type"] = "contains"
        contains["score"] = 60.0

        candidates = pd.concat([exact, startswith, contains], ignore_index=True)
        if candidates.empty:
            return []

        candidates = candidates.assign(
            sab_rank=(candidates["SAB"] != "RXNORM").astype(int),
            suppress_rank=(candidates["SUPPRESS"] != "N").astype(int),
            cvf_rank=(candidates["CVF"] != "4096").astype(int),
            tty_rank=candidates["TTY"].map(TTY_PRIORITY).fillna(99).astype(int),
            name_len=candidates["STR"].str.len(),
        )
        candidates = candidates.sort_values(
            [
                "score",
                "sab_rank",
                "suppress_rank",
                "cvf_rank",
                "tty_rank",
                "name_len",
                "STR",
            ],
            ascending=[False, True, True, True, True, True, True],
        )
        candidates = candidates.drop_duplicates("RXCUI", keep="first").head(limit)

        return [
            ResolutionCandidate(
                concept=RxNormConcept(
                    rxcui=str(row.RXCUI),
                    name=str(row.STR),
                    tty=str(row.TTY) if pd.notna(row.TTY) else None,
                    sab=str(row.SAB) if pd.notna(row.SAB) else None,
                ),
                match_type=str(row.match_type),
                score=float(row.score),
            )
            for row in candidates.itertuples(index=False)
        ]

    def get_concepts(self, rxcuis: set[str]) -> dict[str, RxNormConcept]:
        """Return preferred concept display data for RXCUIs."""

        if not rxcuis:
            return {}

        preferred = self.preferred_names
        rows = preferred[preferred["RXCUI"].isin(rxcuis)]
        concepts = {
            str(row.RXCUI): RxNormConcept(
                rxcui=str(row.RXCUI),
                name=str(row.STR),
                tty=str(row.TTY) if pd.notna(row.TTY) else None,
                sab=str(row.SAB) if pd.notna(row.SAB) else None,
            )
            for row in rows.itertuples(index=False)
        }

        missing = rxcuis - set(concepts)
        if missing:
            fallback = self.rxnconso[self.rxnconso["RXCUI"].isin(missing)]
            for row in fallback.drop_duplicates("RXCUI").itertuples(index=False):
                concepts[str(row.RXCUI)] = RxNormConcept(
                    rxcui=str(row.RXCUI),
                    name=str(row.STR),
                    tty=str(row.TTY) if pd.notna(row.TTY) else None,
                    sab=str(row.SAB) if pd.notna(row.SAB) else None,
                )

        return concepts

    def get_neighborhood(
        self,
        rxcui: str,
        depth: int = 1,
        max_edges: int = 75,
        keep_relations: set[str] | None = None,
    ) -> RxNormNeighborhood:
        """Return a small typed relationship neighborhood around an RXCUI."""

        keep_relations = keep_relations or DEFAULT_RELATIONS
        seen_nodes = {str(rxcui)}
        frontier = {str(rxcui)}
        edge_frames: list[pd.DataFrame] = []
        truncated = False

        rel = self.rxnrel
        for _ in range(max(depth, 1)):
            if not frontier:
                break

            mask = rel["RXCUI1"].isin(frontier) | rel["RXCUI2"].isin(frontier)
            edges = rel[mask].copy()
            edges = edges[edges["RELA"].isin(keep_relations)]
            edges = edges[(edges["RXCUI1"] != "") & (edges["RXCUI2"] != "")]
            edges = edges.drop_duplicates(["RXCUI1", "RXCUI2", "RELA"])

            if len(edges) > max_edges:
                truncated = True
                edges = edges.head(max_edges)

            edge_frames.append(edges)
            next_nodes = set(edges["RXCUI1"].astype(str)) | set(
                edges["RXCUI2"].astype(str)
            )
            frontier = next_nodes - seen_nodes
            seen_nodes |= next_nodes

        if edge_frames:
            edges_df = pd.concat(edge_frames, ignore_index=True).drop_duplicates(
                ["RXCUI1", "RXCUI2", "RELA"]
            )
        else:
            edges_df = pd.DataFrame(columns=["RXCUI1", "RXCUI2", "RELA"])

        if len(edges_df) > max_edges:
            truncated = True
            edges_df = edges_df.head(max_edges)

        rxcuis = set(edges_df["RXCUI1"].astype(str)) | set(
            edges_df["RXCUI2"].astype(str)
        )
        rxcuis.add(str(rxcui))
        concepts = self.get_concepts(rxcuis)

        edges = []
        for row in edges_df.itertuples(index=False):
            source = concepts.get(str(row.RXCUI1))
            target = concepts.get(str(row.RXCUI2))
            if source is None or target is None:
                continue
            edges.append(
                RxNormEdge(
                    source_rxcui=source.rxcui,
                    source_name=source.name,
                    source_tty=source.tty,
                    target_rxcui=target.rxcui,
                    target_name=target.name,
                    target_tty=target.tty,
                    relation=str(row.RELA),
                )
            )

        return RxNormNeighborhood(
            nodes=sorted(
                concepts.values(),
                key=lambda concept: concept.name.casefold(),
            ),
            edges=edges,
            depth=depth,
            truncated=truncated,
        )
