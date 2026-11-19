トラッキングはkdenlive上で手作業で行い、プログラムはGeminiにぶん投げました。
## 依存関係
Linux環境用。PythonとFFmpegが必要。
## 使い方
### render.sh を生成
`$ python3 gen_sh.py`で`render.sh`を生成(元から入っているのでやらなくてok)
### 動画を生成
`$ ./render.sh inmu_gif.mp4 rect.png result.mp4`

> [!IMPORTANT]
> `inmu_king.mp4` は私の著作物ではあり**ません**。`result.mp4`も同様です。他のファイルはこの repository のライセンスファイルに従ってください。
