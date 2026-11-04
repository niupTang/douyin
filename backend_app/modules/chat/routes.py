from flask import Blueprint, jsonify, request

from . import repository


def create_chat_blueprint(service):
    blueprint = Blueprint('chat', __name__, url_prefix='/api/chat')

    @blueprint.errorhandler(ValueError)
    def bad_request(exc):
        return jsonify(code=getattr(exc, 'status', 400), message=str(exc), data=None), getattr(exc, 'status', 400)

    @blueprint.errorhandler(LookupError)
    def missing(exc):
        return jsonify(code=404, message=str(exc), data=None), 404

    @blueprint.get('/conversations')
    def conversations():
        return jsonify(code=200, data=repository.conversations(service.db_path))

    @blueprint.post('/conversations')
    def create():
        return jsonify(code=201, data=repository.create_conversation(service.db_path)), 201

    @blueprint.get('/options')
    def options():
        return jsonify(code=200, data=service.options())

    @blueprint.get('/conversations/<conversation_id>/messages')
    def messages(conversation_id):
        return jsonify(code=200, data=service.get_messages(conversation_id))

    @blueprint.post('/conversations/<conversation_id>/messages')
    def send(conversation_id):
        payload = request.get_json(silent=True) or {}
        return jsonify(code=202, data=service.send(conversation_id, payload.get('prompt'))), 202

    @blueprint.post('/conversations/<conversation_id>/cancel')
    def cancel(conversation_id):
        return jsonify(code=200, data=service.cancel(conversation_id))

    @blueprint.post('/conversations/<conversation_id>/upload')
    def upload(conversation_id):
        if 'file' not in request.files:
            raise ValueError('请选择视频文件')
        return jsonify(code=201, data=service.upload(conversation_id, request.files['file'])), 201

    @blueprint.post('/conversations/<conversation_id>/publish')
    def publish(conversation_id):
        return jsonify(code=202, data=service.publish(conversation_id, request.get_json(silent=True) or {})), 202

    return blueprint
