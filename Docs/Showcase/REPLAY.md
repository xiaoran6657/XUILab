# 公开数据复算与新的实验

公开数据下载和清单SHA见[发布记录](PUBLICATION.md)。历史候选为m4-final-b017672，50次列表与80次渐变；[源码对应](PUBLIC_SOURCE.md)说明公开Git历史和原测量身份的区别。

## 复算已有130次运行

从版本Release下载XUILab-evidence-v0.1.0-preview.1.zip，先按SHA256SUMS核对ZIP，解压到一个新目录，然后在公开仓库根执行：

```powershell
python -B Tools/Publishing/public_evidence.py verify --root <解压后的数据目录> --expected-manifest-sha256 559ce56773e35a96aa464ca8db845831dfd90b610d18fa10717c1939c5fd394f
```

这条命令校验公开文件集合、哈希、身份与成功终态，逐帧复算p50/p95/p99，对照summary及原报告。它不启动Unity。config输出目录已脱敏；receipt与原日志未分发，故此包不能直接交给要求完整原receipt的历史校验器。具体变换和统计局限见[公开数据说明](PUBLIC_DATA.md)。

## 校验素材包

下载XUILab-showcase-v0.1.0-preview.1.zip并核对ZIP哈希，解压到新目录后运行：

```powershell
python -B Tools/Publishing/public_assets.py verify --root <解压后的素材目录> --expected-manifest-sha256 8304f96ede32b5145df30af19352d6057fc4a6fbaacbbb8a8de3cb116262cdb9
```

素材包包含12张PNG、3段MP4、两份完整报告及原被测源清单，共18项。图片和报告同时可从仓库Media/Data读取。视频为45秒帧驱动演示，不反映实时耗时；网站取用规则见[主页交接](WEBSITE_HANDOFF.md)。

## 运行离线检查

使用Python 3.11或更新版本，在仓库根执行：

```powershell
python -m pip install --only-binary=:all: -r Tools/requirements-ci.txt
python -B Tools/Automation/run_checks.py run --run-id local-offline-01 --timeout-seconds 300
python -B -m unittest discover -s Tools/Publishing -p test_*.py -v
python -B Tools/Publishing/check_tracked_assets.py
```

每次换新run-id，不覆盖已有结果。部分完整历史证据集成测试在公开checkout中skip；CI不运行Unity、Player或性能矩阵。标准库调度器与需要NumPy的完整测试依赖分别说明，参见[工具手册](../Agents/REPRODUCIBILITY_PLAYBOOK.md)。

## 生成自己的新实验

使用固定Unity 2022.3.45f1c1打开XUILab/，先完成导入、编译与目标场景核对；按照[Player运行手册](../Agents/BENCHMARK_RUN_PLAYBOOK.md)、对应Experiments协议创建新的源码/构建身份、计划、gate和输出目录。正式采样由确定性Runner驱动，诊断和媒体另行执行。

本Release的Windows演示包是交互展示构建；正式性能数据来自独立Development构建。公开包不包含旧机器完整构建、原运行回执和全部本地生成脚本，不能宣称单靠本Release恢复原实验环境。新的运行应记录自己实际的硬件、版本、测试终态和噪声，不能沿用旧dirty:false、buildId或性能通过结论。
