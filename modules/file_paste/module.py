from core.modules.module_contract import ModuleResult


def run(context):
    context = context or {}
    source_path = context.get("source_path")
    output_dir = context.get("output_dir")
    open_after = context.get("open_after", True)
    if not source_path:
        return ModuleResult(ok=False, message="file_paste module requires source_path. Existing UI still provides the full interactive workflow.", data={"module": "file_paste", "status": "interactive_ui_required"})
    from modules.file_paste.converter import UploadConverter
    result = UploadConverter().convert(
        source_path,
        output_dir,
        open_after=open_after,
        progress_callback=context.get("progress_callback"),
        control=context.get("conversion_control"),
    )
    return ModuleResult(ok=True, message="文件粘贴完成", data=result)
