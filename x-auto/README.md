# RAPOMARU X Auto Post

@rapomaru777 用のX自動投稿準備領域。

## 仕組み
1. `queue.json` に投稿候補を保存
2. GitHub Actions が定期実行
3. `scripts/build_feed.py` が公開時刻を過ぎた投稿だけ `feed.xml` に出力
4. IFTTT の RSS → X 連携が `feed.xml` の新着を検知して自動投稿

## 重要
- X本文は280文字以内
- 「明日の強い店」は保存済み運用ルールに従って作成
- 🌈/🏆は相対順位ではなく絶対評価
- queue内は内部ランキング順
- 投稿時刻までは `feed.xml` に出さない

## RSS URL
https://rapomaru666.github.io/slot-tool/x-auto/feed.xml

## 現在
8/17分は `queue.json` に下書き登録済み。ただし公開時刻は未設定のため、自動投稿は発火しない。
