# app.py
import datetime
import threading
import torch
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_socketio import SocketIO
from transformers import AutoTokenizer, AutoModelForCausalLM, AutoConfig, pipeline, GenerationConfig



# Flaskアプリの初期化
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

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

# モデルのグローバル変数
tokenizer = None
model = None
generation_pipeline = None

def load_model():
    global tokenizer, model, generation_pipeline
    
    print("モデルのロード中...")
    try:
        model_name = "elyza/Llama-3-ELYZA-JP-8B"
        
        # モデルの設定をロード
        config = AutoConfig.from_pretrained(
            model_name,
            trust_remote_code=True
        )
        config.rotary_dim = 32
        config.tie_word_embeddings = True  # 重みを共有するように設定

        # トークナイザーのロード
        tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            trust_remote_code=True,
            use_fast=False
        )

        # モデルのロード
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            config=config,
            trust_remote_code=True,
            torch_dtype=torch.float32,
            low_cpu_mem_usage=True,
            device_map="auto",
            offload_folder="offload"  # オフロードフォルダを指定
        )

        model = model.float()


        # パイプラインの設定
        generation_pipeline = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
            device_map="auto"
        )

        print("モデルロード完了")
    except Exception as e:
        print(f"モデルロードエラー: {e}")
        raise



def generate_commentary(answer_text, topic_prompt):
    try:
        prompt_text = f"""以下の大喜利のお題と回答に対して、75文字以内で簡潔でユーモアのある総評をしてください。
お題: {topic_prompt}
回答: {answer_text}
総評:"""
        
        print(f"Input prompt_text to pipeline: {prompt_text}")
        with torch.no_grad():
            result = generation_pipeline(
                prompt_text,
                max_new_tokens=75,  # max_lengthの代わりにmax_new_tokensを使用
                num_return_sequences=1,
                temperature=0.3,
                top_p=0.3,
                pad_token_id=tokenizer.eos_token_id,
                do_sample=True,
                return_full_text=False  # 入力プロンプトを含まない
            )
            print(f"Pipeline result: {result}")
            # 生成されたテキストから直接総評を取得
            commentary = result[0]['generated_text'].strip()
        if len(commentary) > 75:
            commentary = commentary[:72] + "..."
            
        print(f"Generated commentary: {commentary}")  # デバッグ用
        
        if not commentary or commentary.isspace():
            return "申し訳ありません。もう一度総評を生成してください。"
            
        return commentary
    except Exception as e:
        print(f"Error in generate_commentary: {e}")  # デバッグ用
        return "申し訳ありません。総評の生成中にエラーが発生しました。"

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

    def process_commentary(answer_id, text, topic_prompt):
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                with app.app_context():
                    commentary = generate_commentary(text, topic_prompt)
                    answer = db.session.get(Answer, answer_id)
                    if answer:
                        if commentary != "申し訳ありません。もう一度総評を生成してください。":
                            answer.commentary = commentary
                            db.session.commit()
                            print(f"Commentary saved for answer {answer_id}: {commentary}")
                            # WebSocketを通じて更新を通知
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
    load_model()  # アプリケーション起動時にモデルをロード
    socketio.run(app, debug=True)

