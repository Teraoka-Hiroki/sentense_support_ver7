import math
import re
import json
import warnings
import random
import numpy as np
from typing import List, Dict, Any

# --- 警告の抑制 ---
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# --- Scikit-learn (Surrogate Model用) ---
try:
    from sklearn.svm import SVR
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    HAS_SKLEARN = True
except Exception as e:
    HAS_SKLEARN = False
    print(f"WARNING: scikit-learn import failed. {e}")

# --- External Libraries ---
try:
    import google.generativeai as genai
    import os
    os.environ['GRPC_VERBOSITY'] = 'ERROR'
    os.environ['GLOG_minloglevel'] = '2'
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

try:
    from amplify import BinarySymbolGenerator, FixstarsClient, solve
    HAS_AMPLIFY = True
except ImportError:
    HAS_AMPLIFY = False

class DraftItem:
    def __init__(self, id: int, text: str, type: str, relevance: float, attributes: Dict[str, float], selected: bool = False, user_rating: int = 0):
        self.id = id
        self.text = text
        self.type = type # "Scene Craft" or "Character Dynamics"
        self.relevance = float(relevance)
        self.attributes = attributes # Dict of specific scores
        self.selected = selected
        self.user_rating = int(user_rating) # 1-5, 0=unrated

    def to_dict(self):
        return {
            "id": self.id, "text": self.text, "type": self.type,
            "relevance": self.relevance, "attributes": self.attributes,
            "selected": self.selected, "user_rating": self.user_rating
        }

    @staticmethod
    def from_dict(data):
        return DraftItem(
            id=data["id"], text=data["text"], type=data["type"],
            relevance=data["relevance"], attributes=data["attributes"],
            selected=data.get("selected", False), user_rating=data.get("user_rating", 0)
        )

class LogicHandler:
    
    @staticmethod
    def generate_candidates_api(api_key, topic_main, topic_sub1, topic_sub2, params):
        if not HAS_GENAI: raise Exception("google-generativeai not installed")
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")

        full_topic_context = f"設定1(必須): {topic_main}\n"
        if topic_sub1: full_topic_context += f"設定2: {topic_sub1}\n"
        if topic_sub2: full_topic_context += f"設定3: {topic_sub2}\n"

        prompt = f"""
            以下の執筆テーマ設定に基づき、文章を構成するための「文章ブロック（文または段落）」を「小説の場面設定(Scene Craft)」と「キャラクター・ダイナミクス(Character Dynamics)」について各**5個**（合計10個）生成してください。
            生成する文章ブロックは、設定を考慮してバランスよく分散させてください。
            また、各文章ブロックは異なる観点や情報を提供するようにし、重複を避けてください。

            【小説の場面設定】
            {full_topic_context}

            【シーン・クラフト（描写・演出）のパラメータ設定】
            描写１（説明的－描写的）、描写２（第３者的ー当事者的）、視覚以外の臨場感、思考の開示、会話の緊張感、場面状況（現実的－空想的）

            【キャラクター・ダイナミクスのパラメータ設定】
            登場人物人数、登場人物の精神性、登場人物の信念、過去の因縁、ボイス（語り口）の癖

            出力は必ず以下のJSON形式のリストのみを返してください。Markdown不要。
            [
              {{
                "type": "Scene Craft",
                "text": "...",
                "scores": {{
                   "relevance": 0.0-1.0,
                   "desc_style": 0.0-1.0,
                   "perspective": 0.0-1.0,
                   "sensory": 0.0-1.0,
                   "thought": 0.0-1.0,
                   "tension": 0.0-1.0,
                   "reality": 0.0-1.0
                }}
              }},
              {{
                "type": "Character Dynamics",
                "text": "...",
                "scores": {{
                   "relevance": 0.0-1.0,
                   "char_count": 0.0-1.0,
                   "char_mental": 0.0-1.0,
                   "char_belief": 0.0-1.0,
                   "char_trauma": 0.0-1.0,
                   "char_voice": 0.0-1.0
                }}
              }},
              ...
            ]
            """
        
        response = model.generate_content(prompt)
        text = response.text.replace("```json", "").replace("```", "").strip()
        # 最初の [ と 最後の ] を探してパースする
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1:
            raise Exception("JSON format error from LLM")
            
        data = json.loads(text[start:end+1])
        
        candidates = []
        for i, item in enumerate(data):
            # 属性キーの正規化（念のため）
            scores = item.get("scores", {})
            
            # DraftItemの作成
            candidates.append(DraftItem(
                id=i, 
                text=item["text"], 
                type=item["type"],
                relevance=scores.get("relevance", 0.5),
                attributes=scores
            ))
        
        return candidates

    @staticmethod
    def _create_feature_vector(item: DraftItem) -> List[float]:
        """
        DraftItemからRidge回帰用の特徴ベクトルを作成する。
        シーン用とキャラ用で属性が違うため、固定長のベクトルにマッピングする。
        ベクトル構成: [Relevance, S_Desc, S_Persp, S_Sensory, S_Thought, S_Tension, S_Reality, C_Count, C_Mental, C_Belief, C_Trauma, C_Voice]
        該当しない属性は0.0（または平均値）で埋める。
        """
        # マッピング定義
        vec = []
        vec.append(item.relevance)
        
        # Scene Craft Keys
        s_keys = ["desc_style", "perspective", "sensory", "thought", "tension", "reality"]
        for k in s_keys:
            vec.append(item.attributes.get(k, 0.0)) # ない場合は0.0
            
        # Character Dynamics Keys
        c_keys = ["char_count", "char_mental", "char_belief", "char_trauma", "char_voice"]
        for k in c_keys:
            vec.append(item.attributes.get(k, 0.0))
            
        return vec

    @staticmethod
    def run_optimization(token, candidates_dict, params):
        """パラメータのみに基づく最適化"""
        if not HAS_AMPLIFY: raise Exception("amplify not installed")
        
        candidates = [DraftItem.from_dict(d) for d in candidates_dict]
        if not candidates: return candidates_dict

        gen = BinarySymbolGenerator()
        q = gen.array(len(candidates))

        # 1. パラメータ適合度コスト (ターゲットとの差分)
        h_param_diff = 0
        
        # Scene Craft Targets
        target_s = {
            "desc_style": params['p_desc_style'],
            "perspective": params['p_perspective'],
            "sensory": params['p_sensory'],
            "thought": params['p_thought'],
            "tension": params['p_tension'],
            "reality": params['p_reality']
        }
        # Char Dynamics Targets
        target_c = {
            "char_count": params['p_char_count'],
            "char_mental": params['p_char_mental'],
            "char_belief": params['p_char_belief'],
            "char_trauma": params['p_char_trauma'],
            "char_voice": params['p_char_voice']
        }

        for i, c in enumerate(candidates):
            cost_i = 0
            if c.type == "Scene Craft":
                for k, target_val in target_s.items():
                    val = c.attributes.get(k, 0.5)
                    cost_i += (val - target_val) ** 2
            elif c.type == "Character Dynamics":
                for k, target_val in target_c.items():
                    val = c.attributes.get(k, 0.5)
                    cost_i += (val - target_val) ** 2
            
            # 関連度も考慮 (関連度が高い=1.0に近いほどエネルギーを下げる)
            cost_i -= 2.0 * c.relevance
            
            h_param_diff += cost_i * q[i]

        # 2. 文字数制約
        # 1ブロックあたりの文字数は text length から取得
        current_len = sum([len(c.text) * q[i] for i, c in enumerate(candidates)])
        h_len_penalty = 0.001 * (current_len - float(params['length']))**2

        model = h_param_diff + h_len_penalty

        client = FixstarsClient()
        client.token = token
        client.parameters.timeout = 3000
        
        result = solve(model, client)
        if hasattr(result, 'best'): values = result.best.values
        elif isinstance(result, list) and len(result) > 0: values = result[0].values
        else: return candidates_dict

        for i, c in enumerate(candidates):
            c.selected = (values[q[i]] == 1)
            
        return [c.to_dict() for c in candidates]

    @staticmethod
    def run_bbo_optimization(token, candidates_dict, history, params):
        """
        SVR (Support Vector Regression) を用いたHuman-in-the-Loop最適化
        RidgeからSVRに変更することで、ユーザーの非線形な好み（スイートスポット）を学習可能にする。
        """
        if not HAS_AMPLIFY or not HAS_SKLEARN: raise Exception("Dependencies missing")

        candidates = [DraftItem.from_dict(d) for d in candidates_dict]
        
        # 1. 学習データの準備
        X_train = []
        y_train = []
        
        # 過去の履歴データからベクトルを作成
        for record in history:
            temp_item = DraftItem(0, "", "", record['relevance'], record['attributes'])
            vec = LogicHandler._create_feature_vector(temp_item)
            X_train.append(vec)
            y_train.append(record['rating'])

        # 2. SVRの学習
        # SVRはデータのスケールに敏感なため、StandardScalerを含めたパイプラインにするのが望ましいが
        # 入力データが0.0-1.0の範囲におおむね収まっているため、今回は簡易的にそのままSVRにかける。
        # RBFカーネルを使用し、非線形性を捉える。
        # Cは正則化パラメータ（小さいほど滑らか）、epsilonは不感帯の幅。
        model_svr = SVR(kernel='rbf', C=10.0, epsilon=0.1)
        
        if len(X_train) > 0:
            model_svr.fit(X_train, y_train)
        
        # 現在の候補に対する予測スコアを算出
        current_vectors = [LogicHandler._create_feature_vector(c) for c in candidates]
        
        if len(X_train) > 0:
            predicted_ratings = model_svr.predict(current_vectors)
        else:
            predicted_ratings = [3.0] * len(candidates) # デフォルト

        # 3. Isingマシンの構築
        gen = BinarySymbolGenerator()
        q = gen.array(len(candidates))

        # コスト関数 A: ユーザー予測評価の最大化
        h_user_pref = 0
        weight_pref = 10.0
        for i in range(len(candidates)):
            # 予測スコアをエネルギー項に変換（最大化したいのでマイナスをかける）
            h_user_pref -= weight_pref * predicted_ratings[i] * q[i]

        # コスト関数 B: パラメータ適合度
        # ユーザー評価が少ない場合や、初期段階では設定値（スライダー）も重要
        h_param_diff = 0
        target_s = {
            "desc_style": params['p_desc_style'], "perspective": params['p_perspective'],
            "sensory": params['p_sensory'], "thought": params['p_thought'],
            "tension": params['p_tension'], "reality": params['p_reality']
        }
        target_c = {
            "char_count": params['p_char_count'], "char_mental": params['p_char_mental'],
            "char_belief": params['p_char_belief'], "char_trauma": params['p_char_trauma'],
            "char_voice": params['p_char_voice']
        }

        for i, c in enumerate(candidates):
            cost_i = 0
            if c.type == "Scene Craft":
                for k, target_val in target_s.items():
                    val = c.attributes.get(k, 0.5)
                    cost_i += (val - target_val) ** 2
            elif c.type == "Character Dynamics":
                for k, target_val in target_c.items():
                    val = c.attributes.get(k, 0.5)
                    cost_i += (val - target_val) ** 2
            
            # Relevance
            cost_i -= 1.0 * c.relevance
            h_param_diff += cost_i * q[i]

        # コスト関数 C: 文字数
        current_len = sum([len(c.text) * q[i] for i, c in enumerate(candidates)])
        h_len_penalty = 0.001 * (current_len - float(params['length']))**2

        # 全体の目的関数
        # 学習が進むにつれ、h_user_pref の影響力が支配的になることが期待される
        model = h_user_pref + h_param_diff + h_len_penalty

        client = FixstarsClient()
        client.token = token
        client.parameters.timeout = 3000
        
        result = solve(model, client)
        
        if hasattr(result, 'best'): values = result.best.values
        elif isinstance(result, list) and len(result) > 0: values = result[0].values
        else: return candidates_dict

        for i, c in enumerate(candidates):
            c.selected = (values[q[i]] == 1)
            
        return [c.to_dict() for c in candidates]

    @staticmethod
    def generate_draft(api_key, selected_candidates, params):
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        # 選択された要素を連結
        # 順序は特にないので、リスト順（またはLLMに構成させる）
        materials = "\n\n".join([f"【{item['type']}】\n{item['text']}" for item in selected_candidates])

        prompt_summary = f"""
            以下の小説の断片（シーン描写やキャラクター描写）を統合し、
            一つの小説の場面としての「プロット概要（あらすじ）」を200文字程度で作成してください。
            矛盾がある場合は、より面白い方向に統合してください。

            素材:
            {materials}
            """
        res_summary = model.generate_content(prompt_summary).text

        prompt_article = f"""
            あなたはプロの小説家です。
            以下のプロット概要と素材となる文章ブロックを使用して、小説の一場面を執筆してください。

            【執筆設定】
            目標文字数: {params['length']}文字程度
            
            【プロット概要】
            {res_summary}

            【使用する素材ブロック】
            {materials}

            【指示】
            - 素材をただ繋げるのではなく、一つの物語のシーンとして自然な流れになるように構成・加筆修正してください。
            - 描写は豊かに、会話は自然に。
            - 出力は小説の本文のみ。
            """
        res_article = model.generate_content(prompt_article).text
        return res_summary, res_article

    @staticmethod
    def generate_final(api_key, draft_text, instructions):
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        prompt = f"""
            以下の小説の原稿を、編集者からの指示に基づいて推敲（リライト）してください。

            原稿:
            {draft_text}

            編集者指示:
            {instructions if instructions else "誤字脱字の修正、表現のブラッシュアップ"}

            出力は推敲後の本文のみ。
            """
        return model.generate_content(prompt).text
