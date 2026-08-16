# RAPOMARU X Auto Post

@rapomaru777 用のX自動投稿領域。

## 現行の仕組み
1. 毎日 18:30 JST（09:30 UTC）に GitHub Actions が翌日分の公開スケジュール・過去傾向データを取得
2. `scripts/generate_tomorrow_thread.py` が翌日分を採点し、絶対基準を満たす候補から `thread-YYYY-MM-DD.json` を自動生成
3. 生成時の候補・採点材料は `x-auto/audit/candidates-YYYY-MM-DD.json` に保存
4. 既に手動確定済みの `thread-YYYY-MM-DD.json` がある場合は上書きしない
5. 毎日 20:00 JST（11:00 UTC）に投稿用 GitHub Actions を実行
6. 実行日の翌日に対応する thread ファイルを選択し、全投稿が280文字以内であることを検証
7. Buffer API 経由で X（@rapomaru777）へ投稿
8. 成功時は `x-auto/published.json` に記録し、同じ対象日の重複投稿を防止

## 固定運用ルール
- 毎日夜20:00 JSTに翌日分を自動投稿する
- 原則としてユーザー操作なしで「翌日候補の生成 → 20時投稿」まで実行する
- 投稿先は X アカウント `@rapomaru777`
- 投稿経路は GitHub Actions → Buffer → X
- 本文は280文字以内。超過時は投稿せずエラーにする
- 投稿対象ファイルが存在しない日は安全にスキップする
- `published.json` に投稿済み記録がある対象日は再投稿しない
- 手動で確定した thread ファイルは自動生成で上書きしない
- 「明日の強い店」は関東近郊を対象とする
- 🌈/🏆は相対順位ではなく絶対評価とし、基準未満を上位という理由だけで昇格させない
- 自動生成の基準は原則として 🌈=公開総合評価16.0点以上、🏆=14.0点以上16.0点未満
- 掲載順は採点上位順
- 外部データ取得・解析に失敗した場合は推測で本文を作らず、投稿を安全にスキップする
- 自動生成の元データと判定結果は audit に残し、後から検証できるようにする

## スケジュール
- 18:30 JST: 翌日分 thread 自動生成
- 20:00 JST: Buffer経由で翌日分を X 投稿

## 投稿履歴
`x-auto/published.json` に対象日、Buffer投稿ID、X投稿URL、送信時刻を保存する。

## 旧RSS方式
`feed.xml` / IFTTT 経由の仕組みは旧方式として残っているが、現行のX投稿は Buffer 経由を優先する。
