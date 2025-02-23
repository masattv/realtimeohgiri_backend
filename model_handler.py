import requests
from typing import Optional
import json

class ModelHandler:
    def __init__(self):
        # LM StudioのデフォルトURL
        self.api_base_url = "https://2389-2402-6b00-be46-7100-1581-7c9f-d16d-b48d.ngrok-free.app/v1"
        self.max_retries = 3

    def generate_commentary(self, answer_text: str, topic_prompt: str) -> str:
        """LM Studio APIを使用して総評を生成する"""
        try:
            prompt_text = f"""以下の大喜利のお題と回答に対して、必ず75文字以内で簡潔でユーモアのある総評を書いてください。長すぎる総評は不適切です。

お題: {topic_prompt}
回答: {answer_text}
総評:"""

            # API リクエストの設定
            headers = {
                "Content-Type": "application/json"
            }
            
            # OpenAI APIフォーマットに合わせたリクエストデータ
            data = {
                "model": "local-model",  # モデル名は任意
                "messages": [
                    {
                        "role": "system",
                        "content": "あなたは大喜利の回答に対して簡潔でユーモアのある総評を書く専門家です。"
                    },
                    {
                        "role": "user",
                        "content": prompt_text
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 100
            }

            print(f"Attempting to connect to LM Studio API at: {self.api_base_url}")

            # リトライロジック
            for attempt in range(self.max_retries):
                try:
                    response = requests.post(
                        f"{self.api_base_url}/chat/completions",
                        headers=headers,
                        json=data,
                        timeout=30
                    )
                    
                    print(f"Response status code: {response.status_code}")
                    print(f"Response content: {response.text}")
                    
                    if response.status_code == 200:
                        result = response.json()
                        commentary = result['choices'][0]['message']['content'].strip()
                        
                        # 75文字以内に収める
                        if len(commentary) > 75:
                            commentary = commentary[:72] + "..."
                        
                        print(f"Generated commentary: {commentary}")
                        return commentary
                    
                except requests.exceptions.RequestException as e:
                    print(f"Connection error on attempt {attempt + 1}: {str(e)}")
                    if attempt == self.max_retries - 1:
                        return "申し訳ありません。総評の生成中にエラーが発生しました。"
                    continue

            return "申し訳ありません。総評の生成中にエラーが発生しました。"

        except Exception as e:
            print(f"Error in generate_commentary: {str(e)}")
            return "申し訳ありません。総評の生成中にエラーが発生しました。"


# テスト用のメイン実行コード
if __name__ == "__main__":
    try:
        handler = ModelHandler()
        
        # テスト用の入力
        test_topic = "子供の頃の夢は？"
        test_answer = "宇宙飛行士になって、月でラーメン屋を開くこと"
        
        # 総評を生成
        result = handler.generate_commentary(test_answer, test_topic)
        print("\nテスト結果:")
        print(f"お題: {test_topic}")
        print(f"回答: {test_answer}")
        print(f"総評: {result}")
        
    except Exception as e:
        print(f"エラーが発生しました: {e}") 