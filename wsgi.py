from app import app, socketio
import os

# gunicornで使用するapplication
application = socketio.WSGIApp(app)  # socketioを使用するように変更

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # ポート番号を5000に変更
    socketio.run(
        app,
        host='0.0.0.0',
        port=port
    ) 