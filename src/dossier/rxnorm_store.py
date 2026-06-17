from __future__ import annotations

import re
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

# Term types that denote an active ingredient.
INGREDIENT_TTYS = {"IN", "MIN", "PIN"}

# Relations followed to walk from a specific concept down to its active
# ingredient(s). In the prescribable subset a Semantic Clinical Drug reaches
# its ingredient indirectly (e.g. SCD --consists_of--> SCDC --has_ingredient-->
# IN), so this is a small bounded walk rather than a single hop.
INGREDIENT_PATH_RELATIONS = {
    "has_ingredient",
    "has_ingredients",
    "has_precise_ingredient",
    "consists_of",
    "contains",
}


RXNORM_PRESCRIBABLE_DIR = Path("data/01_raw/rxnorm_prescribable")


def latest_prescribable_release(base: str | Path = RXNORM_PRESCRIBABLE_DIR) -> Path:
    """Return the newest dated RxNorm release folder under ``base``.

    Release folders are named ``YYYYMMDD``, so the lexicographically largest
    name is the most recent release. Dropping in a new dated folder makes it the
    active one with no code change.
    """

    base = Path(base)
    if not base.is_dir():
        raise FileNotFoundError(
            f"RxNorm data folder not found: {base}. See {base}/SOURCE.md for the "
            "expected layout (a YYYYMMDD release folder with rxnconso.parquet and "
            "rxnrel.parquet)."
        )
    releases = sorted(
        (p for p in base.iterdir() if p.is_dir() and p.name.isdigit()),
        key=lambda p: p.name,
    )
    if not releases:
        raise FileNotFoundError(
            f"No dated RxNorm release folders (YYYYMMDD) found in {base}."
        )
    return releases[-1]


def default_rxnorm_paths(
    base: str | Path = RXNORM_PRESCRIBABLE_DIR,
) -> tuple[Path, Path]:
    """Return (rxnconso, rxnrel) parquet paths from the latest release folder."""

    release = latest_prescribable_release(base)
    return release / "rxnconso.parquet", release / "rxnrel.parquet"


def normalize_drug_search_text(value: str) -> str:
    """Normalize punctuation and spacing for forgiving drug-name lookup."""

    normalized = re.sub(r"[^0-9a-zA-Z]+", " ", value.casefold())
    return re.sub(r"\s+", " ", normalized).strip()


def compact_drug_search_text(value: str) -> str:
    """Return a punctuation-free lookup key for dash/space variation."""

    return re.sub(r"[^0-9a-zA-Z]+", "", value.casefold())


class RxNormParquetStore:
    """Read-only RxNorm resolver and graph retriever backed by parquet files."""

    def __init__(
        self,
        rxnconso_path: str | Path | None = None,
        rxnrel_path: str | Path | None = None,
    ) -> None:
        if rxnconso_path is None or rxnrel_path is None:
            default_conso, default_rel = default_rxnorm_paths()
            rxnconso_path = rxnconso_path or default_conso
            rxnrel_path = rxnrel_path or default_rel
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
            self._rxnconso["STR_SEARCH"] = (
                self._rxnconso["STR"].fillna("").map(normalize_drug_search_text)
            )
            self._rxnconso["STR_COMPACT"] = (
                self._rxnconso["STR"].fillna("").map(compact_drug_search_text)
            )
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
        normalized_query = normalize_drug_search_text(drug_name)
        compact_query = compact_drug_search_text(drug_name)
        if not query:
            return []

        df = self.rxnconso
        candidate_frames = []

        exact = df[df["STR_NORM"] == query].copy()
        if not exact.empty:
            exact["match_type"] = "exact"
            exact["score"] = 100.0
            candidate_frames.append(exact)

        if normalized_query and normalized_query != query:
            normalized_exact = df[df["STR_SEARCH"] == normalized_query].copy()
            if not normalized_exact.empty:
                normalized_exact["match_type"] = "normalized_exact"
                normalized_exact["score"] = 96.0
                candidate_frames.append(normalized_exact)

        if compact_query and compact_query != query:
            compact_exact = df[df["STR_COMPACT"] == compact_query].copy()
            if not compact_exact.empty:
                compact_exact["match_type"] = "compact_exact"
                compact_exact["score"] = 94.0
                candidate_frames.append(compact_exact)

        startswith = df[
            (df["STR_NORM"].str.startswith(query)) & (df["STR_NORM"] != query)
        ].copy()
        if not startswith.empty:
            startswith["match_type"] = "prefix"
            startswith["score"] = 80.0
            candidate_frames.append(startswith)

        if normalized_query:
            normalized_startswith = df[
                (df["STR_SEARCH"].str.startswith(normalized_query))
                & (df["STR_SEARCH"] != normalized_query)
            ].copy()
            if not normalized_startswith.empty:
                normalized_startswith["match_type"] = "normalized_prefix"
                normalized_startswith["score"] = 76.0
                candidate_frames.append(normalized_startswith)

        if compact_query:
            compact_startswith = df[
                (df["STR_COMPACT"].str.startswith(compact_query))
                & (df["STR_COMPACT"] != compact_query)
            ].copy()
            if not compact_startswith.empty:
                compact_startswith["match_type"] = "compact_prefix"
                compact_startswith["score"] = 74.0
                candidate_frames.append(compact_startswith)

        contains = df[
            (df["STR_NORM"].str.contains(query, regex=False))
            & (~df["STR_NORM"].str.startswith(query))
        ].copy()
        if not contains.empty:
            contains["match_type"] = "contains"
            contains["score"] = 60.0
            candidate_frames.append(contains)

        if normalized_query:
            normalized_contains = df[
                (df["STR_SEARCH"].str.contains(normalized_query, regex=False))
                & (~df["STR_SEARCH"].str.startswith(normalized_query))
            ].copy()
            if not normalized_contains.empty:
                normalized_contains["match_type"] = "normalized_contains"
                normalized_contains["score"] = 56.0
                candidate_frames.append(normalized_contains)

        if not candidate_frames:
            return []

        candidates = pd.concat(candidate_frames, ignore_index=True)
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

        # Display the concept's *preferred* RxNorm term, not the synonym row that
        # happened to match. A query like "cream" can exact-match an SPL synonym
        # (e.g. RXCUI 1305763's "CREAM", whose preferred name is "milk fat, cow"),
        # and a specific drug like "tretinoin cream" can match an SPL drug-product
        # synonym (TTY DP) when the concept also has a clean RXNORM SCD name. The
        # match_type/score stay tied to the row that actually matched the query.
        preferred = self.get_concepts(
            {str(row.RXCUI) for row in candidates.itertuples(index=False)}
        )

        results: list[ResolutionCandidate] = []
        for row in candidates.itertuples(index=False):
            rxcui = str(row.RXCUI)
            concept = preferred.get(rxcui) or RxNormConcept(
                rxcui=rxcui,
                name=str(row.STR),
                tty=str(row.TTY) if pd.notna(row.TTY) else None,
                sab=str(row.SAB) if pd.notna(row.SAB) else None,
            )
            results.append(
                ResolutionCandidate(
                    concept=concept,
                    match_type=str(row.match_type),
                    score=float(row.score),
                )
            )
        return results

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

    def get_ingredient_concepts(
        self,
        rxcui: str,
        max_hops: int = 2,
    ) -> list[RxNormConcept]:
        """Return active-ingredient concepts (IN/MIN/PIN) reachable from a concept.

        Follows composition/ingredient relations a couple of hops so a specific
        Semantic Clinical Drug can be broadened to its ingredient(s) when it has
        no label evidence of its own. The starting concept is never returned.
        """

        rel = self.rxnrel
        start = str(rxcui)
        # A single ingredient can't be broadened further; expanding from it would
        # walk back out to the co-ingredients of every product that contains it.
        start_concept = self.get_concepts({start}).get(start)
        if start_concept and (start_concept.tty or "") in {"IN", "PIN"}:
            return []

        seen = {start}
        frontier = {start}
        ingredients: dict[str, RxNormConcept] = {}

        for _ in range(max(max_hops, 1)):
            if not frontier:
                break
            mask = rel["RXCUI1"].isin(frontier) | rel["RXCUI2"].isin(frontier)
            edges = rel[mask]
            edges = edges[edges["RELA"].isin(INGREDIENT_PATH_RELATIONS)]
            neighbors = (
                set(edges["RXCUI1"].astype(str)) | set(edges["RXCUI2"].astype(str))
            ) - seen
            if not neighbors:
                break
            seen |= neighbors
            concepts = self.get_concepts(neighbors)
            for candidate in neighbors:
                concept = concepts.get(candidate)
                if concept and (concept.tty or "") in INGREDIENT_TTYS:
                    ingredients[candidate] = concept
            # Ingredients are terminal: don't expand from them, or the walk
            # broadens back out to the co-ingredients of every product that
            # shares this ingredient.
            frontier = neighbors - set(ingredients)

        return sorted(ingredients.values(), key=lambda concept: concept.name.casefold())

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
