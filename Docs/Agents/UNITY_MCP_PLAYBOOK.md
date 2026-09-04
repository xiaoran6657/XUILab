# Unity MCP 操作手册

## 连接基线

工程根：`<repo>/XUILab`。Unity 资产工具使用相对此工程的 `Assets/...` 路径，而 shell／报告可以使用仓库相对路径 `XUILab/Assets/...`。不要把仓库根误传为 Unity project path；`XUILab.sln` 是 IDE 生成入口，不是应手工维护的工程配置。

保留用户已提供的连接方式。下列 TOML 使用单引号字面量，避免 Windows 路径重复转义；这是配置参考，本文不要求重写现有配置或重复启动服务。

```toml
[mcp_servers.unityMCP]
command = '<user-profile>\.local\bin\uvx.exe'
args = ['--offline', '--prerelease', 'explicit', '--from', 'mcpforunityserver>=0.0.0a0', 'mcp-for-unity', '--transport', 'stdio']
startup_timeout_sec = 60
env = { SystemRoot = 'C:\Windows' }
```

官方目前将 stdio 描述为单 Agent 传输，将 HTTP 作为多 Agent 默认方式。因此 XUILab 当前采用单一 MCP 操作者；多 Agent 分工不意味着并行操作编辑器。未来只有实际出现多客户端需求时再评估迁移，不因官网默认不同而擅自改变可用连接。[MCP 官方入口](https://coplaydev.github.io/unity-mcp/getting-started)

## 每次操作前

1. 读取全局 Unity 占用登记，确认任务有相应操作范围。
2. 发现当前 `unityMCP` 工具和资源；优先使用结构化工具，不臆造参数或复用过时 API。
3. 读取实例列表，按完整项目路径识别 XUILab；调用 `set_active_instance` 选择本轮返回的 ID。不能只凭同名工程或上次 ID。
4. 再读取 project info 和 editor state，确认工程根、Unity 版本、场景、Play／暂停、编译／导入、测试和 ready 状态。
5. 涉及场景修改／切换时，另外核实 dirty scene 与 Prefab Stage。ready 不证明场景已保存；不自动丢弃、保存或覆盖用户未保存内容。
6. 明确前后状态恢复约定，并取得唯一操作权。原状态信息缺失时先补读，不能默认 SampleScene 永远是安全测试场景。

本次发现并成功使用的资源包括 `mcpforunity://instances`、`mcpforunity://project/info` 和 `mcpforunity://editor/state`。这些只作为资源名称示例，仍应在实际会话中先发现。当前实例和状态见[环境快照](ENVIRONMENT_BASELINE.md)。

## 按操作类型执行

| 操作 | 执行要点 | 完成证据 |
| --- | --- | --- |
| C#／asmdef 修改 | 先读再改；关联目录和 `.meta` 纳入清单；等待导入编译结束 | 实际编译／Console 结果及相关测试，不只 `is_compiling=false` |
| 场景／Prefab 修改 | 优先结构化工具；使用已授权测试场景，避免修改未知用户场景；保存目标明确 | 资产路径、实际改动、重读结果和必要截图 |
| EditMode／PlayMode 测试 | 记录筛选条件、任务 ID 和启动状态；异步返回后等待终态 | 终态、通过／失败／跳过数量、失败信息、原始结果路径 |
| Windows 构建 | 固定场景清单、目标、后端、Development 配置；使用专属输出目录 | 构建完成结果、日志、构建身份；另做 Player 启动检查 |
| 运行性能 Case | 预先冻结配置，由 C# Runner 控制动作与采样 | 按 run-id 导出的原始样本和有效性结果 |
| 视觉／Profiler 诊断 | 单独诊断运行，记录功能状态和采集设置 | 截图／捕获文件、对应对象或帧、观察说明 |

测试工具返回 success 可能只表示请求成功。未收到终态时标记 not_run／pending 或工具超时，不能填写全部通过。重试前先确认原 job 是否仍运行，避免重叠测试。Console 应区分已有错误与本次新增错误，保留错误文本和来源。

Unity 重载、Play 切换、场景切换后重新查找对象，不缓存上一生命周期的 instance ID。当前工具中的 `manage_ui` 针对 UI Toolkit，不能据名称假设它能操作 UGUI；ListLab／GradientLab 的稳定动作优先通过明确的测试接口或 Runner 驱动。

不得在正式采样窗口进行 MCP 逐帧查询、截图、Frame Debugger、内存快照或 Console 轮询。Profiler 支持的具体计数器需在实际 Unity 版本、平台和构建类型下探测，缺失值不填零。

## 工程与程序集约束

- Runtime、Editor、Tests 分层，测试程序集直接引用被测 Runtime 程序集；运行时代码不引用 `UnityEditor`。
- URP／UGUI／TMP 使用实际 manifest 与 lock 的版本；新增包说明功能需要、兼容验证和锁定结果，不顺便升级全部依赖。
- 参考 LUI 源码先做依赖隔离与实现来源记录，不直接把整个参考目录拖入 `Assets`。
- 新增／移动资产保持 `.meta` 关联和 GUID 稳定；不要为了修复引用批量重建 GUID。
- 不把 `Library`、`.sln`、自动生成 `.csproj` 当成业务源码修改。删除生成缓存不是默认排障第一步。

## 结束与恢复

结束后读取状态，确认测试／Play／构建按约定结束、场景和必要设置得到恢复，再释放占用。需要保持 Play 供用户查看时明确记录，不让后续任务以为编辑器空闲。

断线先重新发现工具和实例，再核对原 job。工具确实不可用时记录失败阶段，可继续源码检查或离线报告；若需要用户在 Unity 打开 MCP 窗口或重连，只提出具体操作及成功信号。不要猜测端口、切换到其他工程、启动第二个服务或杀掉归属不明的进程。

CLI 替代仅在适用授权和工程独占条件下使用；不要让第二个 Editor 同时打开正在操作的同一工程。Windows 后台辅助进程需隐藏窗口，且记录进程归属与停止方式。
