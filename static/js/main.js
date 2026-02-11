// ユーティリティ: ローディング表示
function toggleLoading(show, text="Processing...") {
    const el = document.getElementById('loadingOverlay');
    document.getElementById('loadingText').innerText = text;
    el.style.display = show ? 'flex' : 'none';
}

// テキストエリアの自動リサイズ（動的生成要素用）
function triggerAutoResize() {
    document.querySelectorAll('textarea.auto-expand').forEach(el => {
        if (typeof autoResize === 'function') {
            autoResize(el);
        }
    });
}

// タブ切り替え時にも高さを再計算
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('button[data-bs-toggle="tab"]').forEach(tabEl => {
        tabEl.addEventListener('shown.bs.tab', () => {
            triggerAutoResize();
        });
    });
});

// フォームデータの収集
function getParams() {
    return {
        // Scene Craft
        p_desc_style: parseFloat(document.getElementById('pDescStyle').value),
        p_perspective: parseFloat(document.getElementById('pPerspective').value),
        p_sensory: parseFloat(document.getElementById('pSensory').value),
        p_thought: parseFloat(document.getElementById('pThought').value),
        p_tension: parseFloat(document.getElementById('pTension').value),
        p_reality: parseFloat(document.getElementById('pReality').value),
        // Character Dynamics
        p_char_count: parseFloat(document.getElementById('pCharCount').value),
        p_char_mental: parseFloat(document.getElementById('pCharMental').value),
        p_char_belief: parseFloat(document.getElementById('pCharBelief').value),
        p_char_trauma: parseFloat(document.getElementById('pCharTrauma').value),
        p_char_voice: parseFloat(document.getElementById('pCharVoice').value),
        // Common
        length: parseInt(document.getElementById('pLength').value)
    };
}

function getCommonData() {
    return {
        gemini_key: document.getElementById('geminiKey').value,
        amplify_token: document.getElementById('amplifyToken').value,
        topic_main: document.getElementById('topicMain').value,
        topic_sub1: document.getElementById('topicSub1').value,
        topic_sub2: document.getElementById('topicSub2').value,
        params: getParams()
    };
}

// 候補リストの描画
function renderCandidates(candidates) {
    const container = document.getElementById('candidatesContainer');
    container.innerHTML = '';

    if (!candidates || candidates.length === 0) {
        container.innerHTML = '<div class="alert alert-light text-center p-5">候補はまだありません。Tab 1で生成してください。</div>';
        return;
    }

    // タイプごとにグループ化 (Scene Craft vs Character Dynamics)
    const types = {
        'Scene Craft': candidates.filter(c => c.type === 'Scene Craft'),
        'Character Dynamics': candidates.filter(c => c.type === 'Character Dynamics')
    };

    Object.keys(types).forEach(typeKey => {
        if (types[typeKey].length === 0) return;

        const header = document.createElement('div');
        header.className = 'cluster-header';
        header.innerHTML = `<i class="bi bi-layers me-2"></i> ${typeKey}`;
        container.appendChild(header);

        types[typeKey].forEach(item => {
            const card = document.createElement('div');
            // item.selected (Amplify推奨) ならハイライト
            const optimizedClass = item.selected ? 'optimized-selected' : '';
            card.className = `card card-candidate p-3 ${optimizedClass}`;
            
            // 評価ラジオボタンの生成
            let ratingHtml = '';
            for (let i = 1; i <= 5; i++) {
                const checked = (item.user_rating === i) ? 'checked' : '';
                ratingHtml += `
                    <div class="form-check form-check-inline m-0">
                        <input class="form-check-input" type="radio" name="rating-${item.id}" 
                            id="rating-${item.id}-${i}" value="${i}" ${checked} 
                            onchange="updateUserRating(${item.id}, ${i})">
                        <label class="form-check-label small" for="rating-${item.id}-${i}">${i}</label>
                    </div>
                `;
            }

            // バッジ色分け
            const badgeClass = typeKey === 'Scene Craft' ? 'badge-scene' : 'badge-char';

            card.innerHTML = `
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <span class="section-badge ${badgeClass}">${typeKey}</span>
                    <div class="rating-group">
                        <span class="rating-label">採用度:</span>
                        <span class="small me-2 text-muted">低</span>
                        ${ratingHtml}
                        <span class="small ms-1 text-muted">高</span>
                    </div>
                </div>
                <div class="d-flex gap-2 small mb-2 border-bottom pb-2 candidate-metrics">
                    <span class="fw-bold text-primary"><i class="bi bi-bullseye"></i> Rel: ${item.relevance.toFixed(2)}</span>
                    ${renderSpecificScores(item)}
                </div>
                <p class="card-text mb-0" style="font-size: 0.95rem; line-height: 1.6;">${item.text}</p>
            `;
            container.appendChild(card);
        });
    });
}

function renderSpecificScores(item) {
    // Scene Craft は 6個、Character Dynamics は 5個を英語ラベルで表示
    let html = '';
    if (!item.attributes) return html;

    const sceneKeys = ['desc_style', 'perspective', 'sensory', 'thought', 'tension', 'reality'];
    const charKeys  = ['char_count', 'char_mental', 'char_belief', 'char_trauma', 'char_voice'];

    const labelMap = {
        desc_style: 'desc_style',
        perspective: 'perspective',
        sensory: 'sensory',
        thought: 'thought',
        tension: 'tension',
        reality: 'reality',
        char_count: 'char_count',
        char_mental: 'char_mental',
        char_belief: 'char_belief',
        char_trauma: 'char_trauma',
        char_voice: 'char_voice'
    };

    const keysToUse = item.type === 'Scene Craft' ? sceneKeys : charKeys;

    keysToUse.forEach(key => {
        if (key in item.attributes) {
            const val = item.attributes[key];
            const label = labelMap[key] || key;
            html += `<span class="score-chip"><span class="score-chip-label">${label}</span>${val.toFixed(2)}</span>`;
        }
    });

    return html;
}

// ユーザー評価の一時保存（サーバーには送信せず、メモリ上の状態を更新し、最後にまとめて送信する）
// 注: ここではサーバーへの即時反映はしないが、画面リフレッシュに備えてサーバーへ送る設計にするか、
// あるいは 'runBBOIteration' でまとめて送る。今回は要件により「評価を入力後...ボタンを押すと」なので、
// まとめて送るのが適切だが、JS側で状態を持つ必要がある。
// ここでは簡易的に、サーバーへ都度状態更新を送る形にする（DBレスでシンプルに実装するため）。
async function updateUserRating(id, rating) {
    await fetch('/api/update_rating', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({id: id, rating: rating})
    });
}

// API呼び出し関数群

async function generateCandidates() {
    const data = getCommonData();
    if (!data.gemini_key || !data.topic_main) {
        alert("APIキーと小説の設定1は必須です。");
        return;
    }

    toggleLoading(true, "Geminiで30個の候補を生成中...");
    try {
        const res = await fetch('/api/generate_candidates', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });
        const result = await res.json();
        if (result.status === 'success') {
            renderCandidates(result.candidates);
            document.getElementById('bboHistoryCount').innerText = "学習データ数: 0";
            const tab2 = new bootstrap.Tab(document.getElementById('tab2-tab'));
            tab2.show();
        } else {
            alert("Error: " + result.message);
        }
    } catch (e) {
        alert("通信エラーが発生しました: " + e);
    } finally {
        toggleLoading(false);
    }
}

// パラメータのみで最適化 (User Rating無視)
async function runOptimizationLegacy() {
    const data = getCommonData();
    
    toggleLoading(true, "パラメータ設定のみで最適化計算中...");
    try {
        const res = await fetch('/api/optimize', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });
        const result = await res.json();
        if (result.status === 'success') {
            renderCandidates(result.candidates);
        } else {
            alert("Error: " + result.message);
        }
    } catch (e) {
        alert("通信エラー: " + e);
    } finally {
        toggleLoading(false);
    }
}

// --- BBO / Human-in-the-Loop 関連 ---

async function runBBOIteration() {
    const data = getCommonData();
    
    toggleLoading(true, `ユーザー評価を学習(SVM)し、量子アニーリングで最適化中...`);
    try {
        const res = await fetch('/api/bbo_step', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });
        const result = await res.json();
        if (result.status === 'success') {
            renderCandidates(result.candidates);
            document.getElementById('bboHistoryCount').innerText = `学習データ数: ${result.history_count}`;
            alert("評価を学習しました。最適な組み合わせをハイライトしました。");
        } else {
            alert("Error: " + result.message);
        }
    } catch (e) {
        alert("通信エラー: " + e);
    } finally {
        toggleLoading(false);
    }
}

async function resetBBO() {
    if(!confirm("学習履歴をリセットしますか？")) return;
    
    try {
        const res = await fetch('/api/bbo_reset', { method: 'POST' });
        const result = await res.json();
        if(result.status === 'success') {
             document.getElementById('bboHistoryCount').innerText = "学習データ数: 0";
             // UI上のチェックもリセットしたい場合はリロードが必要だが、
             // ここではカウンターのみリセット
             alert("学習履歴をリセットしました。");
        }
    } catch(e) {
        console.error(e);
    }
}

// ----------------------------------

async function generateDraft() {
    toggleLoading(true, "ドラフト記事を生成中...");
    try {
        const res = await fetch('/api/generate_draft', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({})
        });
        const result = await res.json();
        if (result.status === 'success') {
            document.getElementById('draftSummary').value = result.summary;
            document.getElementById('draftArticle').value = result.article;
            triggerAutoResize();
        } else {
            alert("Error: " + result.message);
        }
    } catch (e) {
        alert("通信エラー: " + e);
    } finally {
        toggleLoading(false);
    }
}

async function generateFinal() {
    const draftContent = {
        article: document.getElementById('draftArticle').value,
        instruction: document.getElementById('addInstruction').value
    };
    
    await fetch('/api/save_draft_edit', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(draftContent)
    });

    toggleLoading(true, "最終記事を生成中...");
    try {
        const res = await fetch('/api/generate_final', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({})
        });
        const result = await res.json();
        if (result.status === 'success') {
            document.getElementById('finalEditor').value = result.final_text;
            triggerAutoResize();
        } else {
            alert("Error: " + result.message);
        }
    } catch (e) {
        alert("通信エラー: " + e);
    } finally {
        toggleLoading(false);
   }
}