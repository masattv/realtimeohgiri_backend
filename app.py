# app.py
import os
import datetime
import threading
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_socketio import SocketIO
from model_handler import ModelHandler

# Flaskアプリの初期化
app = Flask(__name__)

# CORS設定
CORS(app, resources={
    r"/*": {
        "origins": [
            "http://localhost:3000",     # ローカル開発用
            "http://localhost:5173",     # Vite開発サーバー用
            "https://your-production-domain.com",  # 本番環境用（必要に応じて変更）
        ],
        "methods": [
            "GET", 
            "POST", 
            "PUT", 
            "DELETE", 
            "OPTIONS"
        ],
        "allow_headers": [
            "Content-Type",
            "Authorization",
            "Access-Control-Allow-Credentials"
        ],
        "supports_credentials": True  # Cookieを使用する場合は True
    }
})

socketio = SocketIO(app, cors_allowed_origins=[
    "http://localhost:3000",
    "http://localhost:5173",
    "https://your-production-domain.com"
])

# SQLiteを利用したDB設定
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///realtimeohgiri.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# DBモデル
class Topic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prompt = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    deadline = db.Column(db.DateTime, nullable=False)

class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=False)
    answer_text = db.Column(db.Text, nullable=False)
    commentary = db.Column(db.Text)  # AIによる総評
    vote_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

with app.app_context():
    db.create_all()

# モデルハンドラーのインスタンス化
model_handler = ModelHandler()

# generate_commentary関数を削除し、model_handlerを使用するように変更
def process_commentary(answer_id, text, topic_prompt):
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            with app.app_context():
                commentary = model_handler.generate_commentary(text, topic_prompt)
                answer = db.session.get(Answer, answer_id)
                if answer:
                    if commentary != "申し訳ありません。もう一度総評を生成してください。":
                        answer.commentary = commentary
                        db.session.commit()
                        print(f"Commentary saved for answer {answer_id}: {commentary}")
                        socketio.emit('commentary_updated', {
                            'answer_id': answer_id,
                            'commentary': commentary
                        })
                        break
                    else:
                        retry_count += 1
                        if retry_count == max_retries:
                            answer.commentary = "申し訳ありません。総評の生成に失敗しました。"
                            db.session.commit()
        except Exception as e:
            print(f"Error in process_commentary (attempt {retry_count + 1}): {e}")
            retry_count += 1
            if retry_count == max_retries:
                with app.app_context():
                    answer = db.session.get(Answer, answer_id)
                    if answer:
                        answer.commentary = "申し訳ありません。総評の生成に失敗しました。"
                        db.session.commit()

# APIエンドポイント

# すべてのお題情報を取得（トップページ用）
@app.route('/topics', methods=['GET'])
def get_topics():
    topics = Topic.query.order_by(Topic.created_at.desc()).all()
    topic_list = []
    for t in topics:
        answers_count = Answer.query.filter_by(topic_id=t.id).count()
        remaining_time = (t.deadline - datetime.datetime.utcnow()).total_seconds()
        topic_list.append({
            'id': t.id,
            'prompt': t.prompt,
            'remaining_time': max(0, remaining_time),
            'answers_count': answers_count
        })
    return jsonify(topic_list)

# 特定のお題とその回答一覧を取得（投票数順）
@app.route('/topics/<int:topic_id>', methods=['GET'])
def get_topic(topic_id):
    topic = db.session.get(Topic, topic_id)
    if not topic:
        return jsonify({'error': 'Topic not found'}), 404
    answers = Answer.query.filter_by(topic_id=topic_id).order_by(Answer.vote_count.desc()).all()
    answers_list = [{
        'id': ans.id,
        'answer_text': ans.answer_text,
        'commentary': ans.commentary,
        'vote_count': ans.vote_count
    } for ans in answers]
    return jsonify({
        'id': topic.id,
        'prompt': topic.prompt,
        'deadline': topic.deadline.isoformat(),
        'answers': answers_list
    })

# 回答の投稿と非同期でのAI総評生成
@app.route('/topics/<int:topic_id>/answers', methods=['POST'])
def post_answer(topic_id):
    data = request.get_json()
    answer_text = data.get('answer_text')
    if not answer_text:
        return jsonify({'error': 'No answer provided'}), 400
    
    # お題を取得
    topic = db.session.get(Topic, topic_id)
    if not topic:
        return jsonify({'error': 'Topic not found'}), 404
    
    new_answer = Answer(topic_id=topic_id, answer_text=answer_text, commentary="生成中...")
    db.session.add(new_answer)
    db.session.commit()

    thread = threading.Thread(
        target=process_commentary,
        args=(new_answer.id, answer_text, topic.prompt)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({'message': 'Answer submitted', 'answer_id': new_answer.id}), 201

# 回答への投票
@app.route('/answers/<int:answer_id>/vote', methods=['POST'])
def vote_answer(answer_id):
    answer = db.session.get(Answer, answer_id)
    if not answer:
        return jsonify({'error': 'Answer not found'}), 404
    answer.vote_count += 1
    db.session.commit()
    return jsonify({'message': 'Vote counted', 'vote_count': answer.vote_count})

# 新しいお題を追加するエンドポイント

@app.route('/topics/add', methods=['POST'])
def add_topic():
    try:
        data = request.get_json()
        prompt = data.get('prompt')
        
        if not prompt:
            return jsonify({'error': 'No prompt provided'}), 400
            
        # 12時間後を期限として設定
        deadline = datetime.datetime.utcnow() + datetime.timedelta(hours=12)
        
        # 新しいお題をDBに追加
        new_topic = Topic(prompt=prompt, deadline=deadline)
        db.session.add(new_topic)
        db.session.commit()
        
        return jsonify({
            'message': 'Topic added successfully',
            'topic_id': new_topic.id
        }), 201
        
    except Exception as e:
        print(f"Error adding topic: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to add topic'}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_ENV") == "development"
    socketio.run(
        app, 
        debug=debug_mode,  # 本番環境ではFalse
        port=port,
        host='0.0.0.0',  # すべてのインターフェースにバインド
        allow_unsafe_werkzeug=True
    )

