トラッキングはkdenlive上で手作業で行い、プログラムはGeminiにぶん投げました。
## 依存関係
Linux環境用。PythonとFFmpegが必要。
## 使い方
### render.sh を生成
`$ python3 gen_sh.py`で`render.sh`を生成(元から入っているのでやらなくてok)
### 動画を生成
`$ ./render.sh inmu_king_w_audio.mp4 rect.png result.mp4`
## その他
環境によっては`gen_sh.py`の133行目を以下に変更しないといけない可能性があります:
```python
size_expr = build_frame_lookup_expr(size_list, idx_expr="n").replace(",", r"\,")
```

> [!IMPORTANT]
> `inmu_king.mp4` は私の著作物ではあり**ません**。`inmu_king_w_audio`,`result.mp4`も同様です。他のファイルはこの repository のライセンスファイルに従ってください。
