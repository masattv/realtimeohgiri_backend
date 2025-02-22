from app import app, socketio
import os

# gunicornで使用するapplication
application = app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))  # デフォルトポートを10000に変更
    socketio.run(
        app,
        host='0.0.0.0',
        port=port
    ) 