from flask import Blueprint, jsonify, request, send_from_directory
from . import repository as material_repository
from . import service as material_service


def create_materials_blueprint(get_db_path, base_dir):
    blueprint = Blueprint("materials", __name__)

    @blueprint.route('/upload', methods=['POST'])
    def upload_file():
        if 'file' not in request.files:
            return jsonify({
                "code": 200,
                "data": None,
                "msg": "No file part in the request"
            }), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                "code": 200,
                "data": None,
                "msg": "No selected file"
            }), 400
        try:
            generated = material_service.save_temp_upload(file, base_dir)
            return jsonify({"code":200,"msg": "File uploaded successfully", "data": generated}), 200
        except Exception as e:
            return jsonify({"code":200,"msg": str(e),"data":None}), 500


    @blueprint.route('/getFile', methods=['GET'])
    def get_file():
        filename = request.args.get('filename')

        try:
            filename = material_service.sanitize_download_filename(filename)
        except ValueError as exc:
            return {"error": str(exc)}, 400
        return send_from_directory(str(material_service.material_dir(base_dir)), filename)


    @blueprint.route('/uploadSave', methods=['POST'])
    def upload_save():
        if 'file' not in request.files:
            return jsonify({
                "code": 400,
                "data": None,
                "msg": "No file part in the request"
            }), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({
                "code": 400,
                "data": None,
                "msg": "No selected file"
            }), 400

        # 获取表单中的自定义文件名（可选）
        custom_filename = request.form.get('filename', None)
        if custom_filename:
            filename = custom_filename + "." + file.filename.split('.')[-1]
        else:
            filename = file.filename

        try:
            saved = material_service.save_material_upload(
                get_db_path(),
                file,
                base_dir,
                custom_filename=custom_filename,
            )
            print("[OK] 上传文件已记录")

            return jsonify({
                "code": 200,
                "msg": "File uploaded and saved successfully",
                "data": saved
            }), 200

        except Exception as e:
            return jsonify({
                "code": 500,
                "msg": str("upload failed!"),
                "data": None
            }), 500


    @blueprint.route('/getFiles', methods=['GET'])
    def get_all_files():
        try:
            data = material_repository.list_file_records(get_db_path())
            return jsonify({
                "code": 200,
                "msg": "success",
                "data": data
            }), 200
        except Exception as e:
            return jsonify({
                "code": 500,
                "msg": str("get file failed!"),
                "data": None
            }), 500


    @blueprint.route('/deleteFile', methods=['GET'])
    def delete_file():
        file_id = request.args.get('id')

        if not file_id or not file_id.isdigit():
            return jsonify({
                "code": 400,
                "msg": "Invalid or missing file ID",
                "data": None
            }), 400

        try:
            record = material_repository.delete_file_record(get_db_path(), file_id)
            if not record:
                return jsonify({
                    "code": 404,
                    "msg": "File not found",
                    "data": None
                }), 404

            return jsonify({
                "code": 200,
                "msg": "File deleted successfully",
                "data": {
                    "id": record['id'],
                    "filename": record['filename']
                }
            }), 200

        except Exception as e:
            return jsonify({
                "code": 500,
                "msg": str("delete failed!"),
                "data": None
            }), 500

    return blueprint
