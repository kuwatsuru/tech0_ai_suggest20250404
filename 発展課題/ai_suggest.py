import openai
import os
import json
import difflib
from dotenv import load_dotenv
import streamlit as st

#Streamlit cloud用にキー読み込み
api_key = st.secrets.openai.OPENAI_API_KEY
client = openai.OpenAI(api_key=api_key)

# .env を読み込む
# load_dotenv(dotenv_path=r"C:\Users\kosuk\Documents\Programing\python_files\Tech0_202504_アプリ開発\発展課題\.env.vb")

# 環境変数から OpenAI API キーを取得
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY が設定されていません。")

client = openai.OpenAI(api_key=api_key)


def load_reference_list(json_file):
    """JSONファイルからやりたいことリストを読み込む"""
    with open(json_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def find_best_match(query, reference_list, threshold=0.4):
    """
    ユーザーのクエリに対して最も類似度の高い「やりたいこと」のエントリを探索する。
    部分一致があればその候補を返し、なければ difflib による類似度評価を実施します。
    """
    # 文字列の部分一致チェック
    candidates = [entry for entry in reference_list if query in entry["やりたいこと"]]
    # 部分一致がなければ Fuzzy マッチング
    if not candidates:
        scores = []
        for entry in reference_list:
            ratio = difflib.SequenceMatcher(None, query, entry["やりたいこと"]).ratio()
            scores.append((ratio, entry))
        best_match = max(scores, key=lambda x: x[0])
        if best_match[0] >= threshold:
            candidates = [best_match[1]]
    return candidates[0] if candidates else None


def suggest_ideas_with_rag(want_title):
    """
    Function Calling を使用しない通常の出力モードです。
    ユーザーのやりたいことと参考情報を組み込んだプロンプトを作成し、
    AI に回答（費用、期間、最初のステップ）をテキストで出力させます。
    """
    reference_list = load_reference_list("reference_list.json")
    reference_entry = find_best_match(want_title, reference_list)
    
    if reference_entry:
        ref_text = (
            f"参考情報: 費用: {reference_entry['費用']} / 期間: {reference_entry['時間']} / "
            f"最初のステップ: {' / '.join(reference_entry['実現のためにやるべきこと'])}"
        )
    else:
        ref_text = "参考情報は見つかりませんでした。"
    
    prompt = f"""
    私は「{want_title}」を実現したいと考えています。
    以下の3項目を日本語で簡潔に出力してください：
    - 費用（例：5万円）
    - 期間（例：3ヶ月）
    - 最初のステップ（例：まずは本を買って基礎を学ぶ / 学校に通う）
    
    また、以下の参考情報を考慮して回答を強化してください：
    {ref_text}
    
    出力は以下の形式でお願いします：
    
    ・費用: ○○
    ・期間: △△
    ・最初のステップ: □□ / xx / ･･･
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "あなたはやりたいことを具体的に分析するアシスタントです。"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.7
        )
        suggestion_text = response.choices[0].message.content.strip()
        return suggestion_text
    except Exception as e:
        return f"APIエラーが発生しました: {e}"

def suggest_ideas_with_rag_and_function_call(want_title):
    """
    Function Calling を利用する出力モードです。
    リファレンス情報をプロンプトに組み込み、関数呼び出しの仕組みを利用して
    費用、期間、最初のステップを構造化出力します。
    """
    reference_list = load_reference_list("reference_list.json")
    reference_entry = find_best_match(want_title, reference_list)
    
    if reference_entry:
        ref_text = (
            f"参考情報: 費用: {reference_entry['費用']} / 期間: {reference_entry['時間']} / "
            f"最初のステップ: {' / '.join(reference_entry['実現のためにやるべきこと'])}"
        )
    else:
        ref_text = "参考情報は見つかりませんでした。"
    
    prompt = f"""
    私は「{want_title}」を実現したいと考えています。
    以下の3項目を日本語で簡潔に出力してください：
    - 費用（例：5万円）
    - 期間（例：3ヶ月）
    - 最初のステップ（例：まずは本を買って基礎を学ぶ / 学校に通う）
    
    また、以下の参考情報を考慮して回答を強化してください：
    {ref_text}
    """
    
    function_spec = {
        "name": "provide_idea_details",
        "description": "やりたいことに対する、費用、期間、最初のステップを返します。",
        "parameters": {
            "type": "object",
            "properties": {
                "費用": {
                    "type": "integer",
                    "description": "実現に必要な概算の費用"
                },
                "期間": {
                    "type": "integer",
                    "description": "実現するために必要な期間を月数で表示"
                },
                "最初のステップ": {
                    "type": "string",
                    "description": "プロジェクト開始時に取り組むべき3つの具体的手順"
                }
            },
            "required": ["費用", "期間", "最初のステップ"]
        }
    }
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "あなたはやりたいことに対して費用、期間、開始時のステップを具体的に分析するアシスタントです。"},
                {"role": "user", "content": prompt}
            ],
            functions=[function_spec],
            function_call="auto",
            max_tokens=300,
            temperature=0.7
        )
        message = response.choices[0].message
        if message.function_call is not None:
            arguments = message.function_call.arguments
            result = json.loads(arguments)
            formatted_result = (
                f"【費用(円）】: {result.get('費用')}\n"
                "\n"
                f"【期間（月)】: {result.get('期間')}\n"
                "\n"
                f"【最初のステップ】: {result.get('最初のステップ')}"
            )
            return formatted_result
        else:
            return message.content if message.content is not None else "返答が得られませんでした。"
    except Exception as e:
        return f"APIエラーが発生しました: {e}"

# Streamlit の UI 設定
st.title("やりたいことサジェストアプリ")

# ユーザーに「やりたいこと」と出力モードを入力させる

want_title = st.text_input("やりたいことを入力してEnterを押してください:", "")
mode = st.radio("出力モードを変更可能です：", options=["通常出力", "Function Calling 出力"])


if want_title:
    if mode == "通常出力":
        output = suggest_ideas_with_rag(want_title)
    else:
        output = suggest_ideas_with_rag_and_function_call(want_title)
    st.write(output)
