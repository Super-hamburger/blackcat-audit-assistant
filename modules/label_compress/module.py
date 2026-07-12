from core.modules.module_contract import ModuleResult


def run(context):
    context = context or {}
    pdf_path = context.get("pdf_path") or context.get("pdf_paths")
    output_dir = context.get("output_dir")
    if not pdf_path:
        return ModuleResult(ok=False, message="label_compress module requires pdf_path/pdf_paths. Existing UI still provides the full interactive workflow.", data={"module": "label_compress", "status": "interactive_ui_required"})
    from modules.label_compress.processor import LabelProcessor
    processor = LabelProcessor(
        pdf_path,
        output_dir,
        batch_size=context.get("batch_size", 90),
        auto_zip=context.get("auto_zip", True),
        open_output=context.get("open_output", True),
        cancel_token=context.get("cancel_token"),
        min_run_seconds=context.get("min_run_seconds", 2.0),
    )
    result = processor.run(
        on_progress=context.get("on_progress"),
        on_log=context.get("on_log"),
        on_stats=context.get("on_stats"),
    )
    return ModuleResult(ok=bool(result.get("success")), message="面单压缩完成" if result.get("success") else "面单压缩失败", data=result)
