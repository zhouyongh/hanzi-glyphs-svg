# viewer

`index.html` 由 `python src/build_viewer.py` 生成，**不入库**（见 `.gitignore`）。

- 本地预览：先运行 `python src/build_viewer.py`，再打开 `viewer/index.html`。
- 线上：`.github/workflows/pages.yml` 在部署时生成到站点根 `_site/index.html`。
- 不要手改 `index.html`；改模板请改 `src/build_viewer.py` 后重新生成。
