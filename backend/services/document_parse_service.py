import json
import logging
import os
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DocumentParseService:
    """Parse documents into JSON chunks with rich metadata.

    Goal (minimal change):
      - Provide a single entry point for "Parse File" that can convert tables/images into text
        when using Unstructured.
      - Keep output compatible with other parts of this repo: top-level fields + `chunks` list.

    Output schema (kept consistent with 01-loaded-docs):
      {
        "filename": str,
        "total_chunks": int,
        "total_pages": int,
        "parsing_backend": str,
        "parsing_method": str,
        "timestamp": str,
        "chunks": [ {"content": str, "metadata": {...}} ]
      }
    """

    def parse_file(
        self,
        file_path: str,
        *,
        backend: str,
        method: str,
        filename: Optional[str] = None,
        # Unstructured params
        strategy: str = "hi_res",
        include_header_footer: Optional[bool] = None,
        infer_table_structure: Optional[bool] = True,
        extract_images_in_pdf: Optional[bool] = True,
        languages: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> dict:
        if not filename:
            filename = os.path.basename(file_path)

        if backend == "unstructured":
            return self._parse_with_unstructured(
                file_path,
                filename=filename,
                method=method,
                strategy=strategy,
                include_header_footer=include_header_footer,
                infer_table_structure=infer_table_structure,
                extract_images_in_pdf=extract_images_in_pdf,
                languages=languages,
                **kwargs,
            )

        raise ValueError(f"Unsupported parsing backend: {backend}")

    def _parse_with_unstructured(
        self,
        file_path: str,
        *,
        filename: str,
        method: str,
        strategy: str,
        include_header_footer: Optional[bool],
        infer_table_structure: Optional[bool],
        extract_images_in_pdf: Optional[bool],
        languages: Optional[list[str]],
        **kwargs: Any,
    ) -> dict:
        try:
            from unstructured.partition.pdf import partition_pdf
        except Exception as e:  # pragma: no cover
            raise ValueError(
                "Unstructured parsing requested but dependency is missing. Install `unstructured` and its PDF extras."
            ) from e

        params: dict[str, Any] = {"strategy": strategy}
        if include_header_footer is not None:
            params["include_header_footer"] = include_header_footer
        if infer_table_structure is not None:
            params["infer_table_structure"] = infer_table_structure
        if extract_images_in_pdf is not None:
            params["extract_images_in_pdf"] = extract_images_in_pdf
        if languages is not None:
            params["languages"] = languages
        params.update(kwargs)

        elements = partition_pdf(file_path, **params)

        chunks = []
        pages = set()

        for idx, elem in enumerate(elements, 1):
            # elem text
            content = str(elem).strip()
            if not content:
                continue

            # metadata
            md = {}
            try:
                md_raw = elem.metadata.__dict__
            except Exception:
                md_raw = {}

            # keep json-serializable
            for k, v in md_raw.items():
                if k == "_known_field_names":
                    continue
                try:
                    json.dumps({k: v})
                    md[k] = v
                except Exception:
                    md[k] = str(v)

            page_number = md.get("page_number") or md.get("page")
            if page_number is not None:
                pages.add(int(page_number))

            md.update(
                {
                    "chunk_id": len(chunks) + 1,
                    "page_number": int(page_number) if page_number is not None else None,
                    "element_type": elem.__class__.__name__,
                    "category": str(getattr(elem, "category", None)),
                    "id": str(getattr(elem, "id", None)),
                    "parse_method": method,
                }
            )

            chunks.append({"content": content, "metadata": md})

        return {
            "filename": filename,
            "total_chunks": len(chunks),
            "total_pages": max(pages) if pages else 0,
            "parsing_backend": "unstructured",
            "parsing_method": method,
            "timestamp": datetime.now().isoformat(),
            "chunks": chunks,
        }
