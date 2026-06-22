# PROJECT_STRUCTURE_REPORT

整理日期：2026-06-21

## 1. 最终目录树

```text
MountainRS/
  PROJECT_STRUCTURE_REPORT.md
  MRS Obsidian/
    Mountain RS Foundation Project/
      .obsidian/
      00_Index/
      01_Stage_Index/
        Stage 1｜GeoTIFF 栅格体检闭环.md
      02_Tasks/
      03_Concepts/
        Concept_GeoTIFF.md
      04_Results/
        Result_GeoTIFF_体检实验_01.md
      05_Code_Templates/
        Code Template｜GeoTIFF Health Check.md
      06_Errors/
      07_Physics_Gates/
      08_Understanding_Gates/
  stage1_geotiff_health/
    data/
      srtm_dem.tif
    scripts/
      geotiff_health_check.py
      __pycache__/
    outputs/
      geotiff_band1_preview.png
    reports/
      geotiff_health_check_report.md
    obsidian_drafts/
      .obsidian/
      geotiff_health_check_report.md
    requirements.txt
  stage2_dem_terrain/
    data/
      srtm_dem.tif
    scripts/
    outputs/
    reports/
    obsidian_drafts/
```

说明：`.DS_Store` 等系统文件仍保留在原处，未删除。

## 2. 已移动或重命名的文件与目录

- `MRS Obsidian/Mountain RS Foundation Project/Stage 1｜GeoTIFF 栅格体检闭环.md`
  -> `MRS Obsidian/Mountain RS Foundation Project/01_Stage_Index/Stage 1｜GeoTIFF 栅格体检闭环.md`
- `stage1_geotiff_health/obsidian/Concept_GeoTIFF.md`
  -> `MRS Obsidian/Mountain RS Foundation Project/03_Concepts/Concept_GeoTIFF.md`
- `stage1_geotiff_health/obsidian/Result_GeoTIFF_体检实验_01.md`
  -> `MRS Obsidian/Mountain RS Foundation Project/04_Results/Result_GeoTIFF_体检实验_01.md`
- `stage1_geotiff_health/obsidian/Code Template｜GeoTIFF Health Check.md`
  -> `MRS Obsidian/Mountain RS Foundation Project/05_Code_Templates/Code Template｜GeoTIFF Health Check.md`
- `stage1_geotiff_health/obsidian/`
  -> `stage1_geotiff_health/obsidian_drafts/`
- `stage2_dem_terrain/obsidian/`
  -> `stage2_dem_terrain/obsidian_drafts/`

同时创建了正式 Obsidian 库中的 `00_Index` 到 `08_Understanding_Gates` 目录。

## 3. 未移动的文件与原因

- `stage1_geotiff_health/reports/geotiff_health_check_report.md`：程序输出报告，按要求保留在 `reports/`。
- `stage1_geotiff_health/obsidian_drafts/geotiff_health_check_report.md`：原位于 stage1 草稿 Obsidian 目录，不属于本次指定的正式库归档映射；整理后保留在草稿区。
- `stage1_geotiff_health/data/`、`scripts/`、`outputs/`、`reports/`：按规则保留在 stage1 文件夹内。
- `stage2_dem_terrain/data/`、`scripts/`、`outputs/`、`reports/`：按规则保留在 stage2 文件夹内。
- `Task｜GeoTIFF 栅格体检闭环.md`：当前项目中未发现该文件，因此没有可移动对象。
- `Concept｜GeoTIFF.md`：当前项目中未发现该文件；已移动存在的 `Concept_GeoTIFF.md`。
- `Result｜GeoTIFF 体检实验 01.md`：当前项目中未发现该文件；已移动存在的 `Result_GeoTIFF_体检实验_01.md`。

## 4. 重复文件检查

存在以下内容重复：

- `stage1_geotiff_health/reports/geotiff_health_check_report.md`
- `stage1_geotiff_health/obsidian_drafts/geotiff_health_check_report.md`

两者 SHA1 均为：

```text
616623189962590b6a37c35998e16e1959e6d604
```

存在以下 DEM 数据副本：

- `stage1_geotiff_health/data/srtm_dem.tif`
- `stage2_dem_terrain/data/srtm_dem.tif`

两者 SHA1 均为：

```text
7e8f0053a499c72e317e16d7d6721bde6e6ebceb
```

未删除任何重复文件。

## 5. Stage 2 前建议确认

- 确认 `stage2_dem_terrain/data/srtm_dem.tif` 是否应作为 Stage 2 的正式输入，还是只保留一份跨 stage 共享数据。
- 确认是否需要补写 `02_Tasks/Task｜GeoTIFF 栅格体检闭环.md`，因为当前项目未发现该任务笔记。
- 确认 `stage1_geotiff_health/obsidian_drafts/geotiff_health_check_report.md` 是否只是 `reports/` 输出报告的历史副本。
- 确认正式 Obsidian 库只使用 `MRS Obsidian/Mountain RS Foundation Project/`，stage 内 `obsidian_drafts/` 仅作 Codex 草稿区。
- 进入 Stage 2 前，再检查 DEM 坐标系、NoData、分辨率、范围和垂直单位；本次整理未执行任何 DEM 处理。
