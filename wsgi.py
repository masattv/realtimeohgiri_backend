from app import app, socketio
import os

# gunicornで使用するapplication
application = socketio.WSGIApp(app)

if __name__ == "__main__":
    # Render環境かどうかを確認
    is_render = os.environ.get("RENDER") == "true"
    
    if is_render:
        # Render環境では環境変数PORTを使用
        port = int(os.environ.get("PORT", 10000))
    else:
        # ローカル環境ではデフォルトポート5000を使用
        port = 5000

    socketio.run(
        app,
        host='0.0.0.0',
        port=port,
        debug=not is_render  # Render環境ではデバッグモードをオフ
    ) 