from core.modules.module_contract import ModuleResult


def run(context):
    context = context or {}
    required = ("source_path", "finished_path", "pdf_paths", "output_dir")
    missing = [key for key in required if not context.get(key)]
    if missing:
        return ModuleResult(
            ok=False,
            message=f"label_printing module requires: {', '.join(missing)}",
            data={},
        )

    from modules.label_printing.processor import LabelPrintProcessor

    processor = LabelPrintProcessor(
        context["source_path"],
        context["finished_path"],
        context["pdf_paths"],
        context["output_dir"],
        context.get("scope", "all"),
        bool(context.get("split_types", False)),
        bool(context.get("open_after", True)),
    )
    result = processor.run(progress_callback=context.get("progress_callback"))
    return ModuleResult(ok=True, message="面单打印完成", data=result)
