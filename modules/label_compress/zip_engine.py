from pathlib import Path
import zipfile

class ZipEngine:
    def zip_folder(self, folder_path, zip_path):
        folder_path = Path(folder_path)
        zip_path = Path(zip_path)
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as z:
            for file_path in folder_path.rglob("*"):
                if file_path.is_file():
                    z.write(file_path, arcname=file_path.relative_to(folder_path.parent))
