# viewer

`index.html` 是**提交进仓库的静态预览**（由 `python src/build_viewer.py` 生成，勿手改）。

- 本地预览：直接打开 `viewer/index.html`。
- 数据变化后运行 `python src/build_viewer.py` 重新生成，并提交更新。
- 线上：`.github/workflows/pages.yml` 直接发布这份文件。
