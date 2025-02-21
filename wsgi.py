from app import app, socketio
import os

# このファイルはgunicornによって直接使用される
application = socketio.run(
    app,
    host='0.0.0.0',
    port=int(os.environ.get("PORT", 5000))
) 