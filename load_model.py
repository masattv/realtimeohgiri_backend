import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, AutoConfig
import os

def load_and_save_model():
    print("モデルのロード中...")
    try:
        model_name = "weblab-GENIAC/Tanuki-8B-dpo-v1.0"
        save_directory = "saved_model"
        
        # モデルの設定をロード
        config = AutoConfig.from_pretrained(
            model_name,
            trust_remote_code=True
        )

        # トークナイザーのロード
        tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            trust_remote_code=True,
            use_fast=False
        )

        # モデルのロード - メモリ使用量を最適化
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            config=config,
            trust_remote_code=True,
            torch_dtype=torch.float32,
            low_cpu_mem_usage=True
        )

        # モデルとトークナイザーを保存
        os.makedirs(save_directory, exist_ok=True)
        model.save_pretrained(save_directory)
        tokenizer.save_pretrained(save_directory)
        print("モデルの保存完了")

    except Exception as e:
        print(f"モデルロードエラー: {e}")
        raise

if __name__ == "__main__":
    load_and_save_model() 