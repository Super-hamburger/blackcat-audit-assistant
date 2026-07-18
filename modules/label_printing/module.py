from pathlib import Path

from core.modules.module_contract import ModuleResult


def run(context):
    context = context or {}
    required = ("pdf_paths", "output_dir")
    missing = [key for key in required if not context.get(key)]
    if missing:
        return ModuleResult(
            ok=False,
            message=f"label_printing module requires: {', '.join(missing)}",
            data={},
        )

    if any(not Path(path).is_file() for path in context["pdf_paths"]):
        return ModuleResult(
            ok=False,
            message="label_printing module requires valid pdf_paths",
            data={},
        )

    from modules.label_printing.processor import PdfOnlyLabelPrintProcessor

    processor = PdfOnlyLabelPrintProcessor(
        context["pdf_paths"],
        context["output_dir"],
        context.get("scope", "all"),
        bool(context.get("split_types", False)),
        bool(context.get("open_after", True)),
    )
    result = processor.run(progress_callback=context.get("progress_callback"))
    return ModuleResult(ok=True, message="面单打印完成", data=result)
