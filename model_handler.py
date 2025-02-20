import requests
from typing import Optional
import json

class ModelHandler:
    def __init__(self):
        self.api_base_url = "https://45b2-2402-6b00-be46-7100-4c56-e1a4-311e-260a.ngrok-free.app"  # LM StudioのデフォルトURL
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
            
            data = {
                "messages": [
                    {"role": "user", "content": prompt_text}
                ],
                "temperature": 0.7,
                "max_tokens": 100,
                "stop": ["\n"],  # 改行で生成を停止
                "stream": False
            }

            # リトライロジック
            for attempt in range(self.max_retries):
                try:
                    response = requests.post(
                        f"{self.api_base_url}/chat/completions",
                        headers=headers,
                        json=data,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        commentary = result['choices'][0]['message']['content'].strip()
                        
                        # 75文字以内に収める
                        if len(commentary) > 75:
                            commentary = commentary[:72] + "..."
                        
                        print(f"Generated commentary: {commentary}")
                        return commentary
                    
                except requests.exceptions.RequestException as e:
                    if attempt == self.max_retries - 1:
                        print(f"API request failed after {self.max_retries} attempts: {e}")
                        return "申し訳ありません。総評の生成中にエラーが発生しました。"
                    continue

            return "申し訳ありません。総評の生成中にエラーが発生しました。"

        except Exception as e:
            print(f"Error in generate_commentary: {e}")
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