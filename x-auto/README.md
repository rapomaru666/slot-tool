# RAPOMARU X Auto Post

@rapomaru777 用のX自動投稿領域。

## 現行の仕組み
1. 翌日分の確定本文を `x-auto/thread-YYYY-MM-DD.json` に保存
2. GitHub Actions を毎日 20:00 JST（11:00 UTC）に実行
3. 実行日の翌日の日付に対応する thread ファイルを自動選択
4. 各投稿が280文字以内であることを投稿直前に検証
5. Buffer API 経由で X（@rapomaru777）へ投稿
6. 成功した投稿は `x-auto/published.json` に記録し、同じ対象日の重複投稿を防止

## 固定運用ルール
- 毎日夜20:00 JSTに翌日分を自動投稿する
- 投稿先は X アカウント `@rapomaru777`
- 投稿経路は GitHub Actions → Buffer → X を基本とする
- 本文は280文字以内。超過時は投稿せずエラーにする
- `thread-YYYY-MM-DD.json` が存在しない日は安全にスキップする
- `published.json` に投稿済み記録がある対象日は再投稿しない
- 「明日の強い店」は保存済み運用ルールに従って作成する
- 🌈/🏆は相対順位ではなく絶対評価
- 掲載順は内部ランキング上位順を基本とする

## 投稿履歴
`x-auto/published.json` に対象日、Buffer投稿ID、X投稿URL、送信時刻を保存する。

## 旧RSS方式
`feed.xml` / IFTTT 経由の仕組みは旧方式として残っているが、現行のX投稿は Buffer 経由を優先する。
