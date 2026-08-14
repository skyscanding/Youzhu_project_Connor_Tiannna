# 贡献指南（致 Tiannna）

> 这份指南是给 **Tiannna** 的贡献说明——欢迎加入！本仓库是"城市更新合规参谋 Agent"原型，
> 所有改动请遵循下面的流程，保证 main 分支始终可用。

## 一、工作流程（Fork + PR）

1. **Fork 本仓库**：打开仓库页 → 右上角 **Fork**，复制到你自己的账号下；
2. **克隆你的 fork**，并把本仓库设为上游（upstream）：

   ```bash
   git clone https://github.com/<你的账号>/Youzhu_project_Connor_Tiannna.git
   cd Youzhu_project_Connor_Tiannna
   git remote add upstream https://github.com/skyscanding/Youzhu_project_Connor_Tiannna.git
   ```

3. **每次开工前同步上游**：

   ```bash
   git fetch upstream
   git checkout main
   git merge upstream/main
   ```

4. **开分支开发**（永远不要直接提交到 main）：

   ```bash
   git checkout -b feature/你做的功能        # 或 fix/修复的问题
   # ... 开发、本地测试 ...
   ```

5. **提交**（消息格式见下）→ **推送到你的 fork** → 在 GitHub 上发起 **Pull Request**：
   ```bash
   git push origin feature/你做的功能
   ```
   PR 描述请写清：改了什么（What）、为什么（Why）、怎么验证的（Testing）。

## 二、提交信息格式（Conventional Commits）

```
<type>(<scope>): <subject>

示例：
feat(scale): 新增奖励系数切换的规模传导计算
fix(webapp): 修复政策查询在空结果时的报错
docs(readme): 补充模块说明
test(compliance): 新增总量预警边界用例
```

| type | 含义 |
|------|------|
| `feat` | 新功能 |
| `fix` | 修复 bug |
| `docs` | 文档 |
| `test` | 测试 |
| `refactor` | 重构（行为不变） |
| `perf` | 性能优化 |
| `chore` | 杂务（依赖、配置等） |

## 三、本地测试（提交前必跑）

```bash
# 主数据层（Youzhu）
cd Youzhu
pip install -r requirements.txt
python -m pytest -q            # 当前 152 个测试，必须全绿

# 迭代开发版（Fork1，含规模传导与 WebApp）
cd ../Fork1
pip install -r requirements.txt
python -m pytest -q            # 当前 198 个测试，必须全绿
```

**规则**：
- 新功能必须**先写测试再写代码**（TDD），关键逻辑覆盖率 ≥80%；
- 所有测试通过前不要发起 PR；
- CI（GitHub Actions）会在每次 PR 自动重跑以上两套测试，红了会被拦下。

## 四、PR 检查清单

- [ ] 分支名符合 `feature/xxx` 或 `fix/xxx`
- [ ] 提交信息符合 Conventional Commits 格式
- [ ] Youzhu 与 Fork1 两套测试全部通过
- [ ] 新功能带有测试（TDD 证据：测试先红后绿）
- [ ] 没有把运行时产物/缓存提交进来（`data/snapshot/`、`data/reports/`、`__pycache__/` 等已在 .gitignore）
- [ ] 数据类改动遵守"不虚构"红线：发文号/日期/链接未知一律留空，不编造

## 五、常见问题

- **国内访问 GitHub 慢**：clone 可用镜像加速，或改用 SSH（`git remote set-url origin git@github.com:<你的账号>/Youzhu_project_Connor_Tiannna.git`，需先配置 SSH key）；
- **测试与本地不一致**：先 `git pull upstream main` 同步，再重跑；
- **改错了想撤回**：`git reset --soft HEAD~1`（保留改动）或 `git checkout -- <文件>`（丢弃单文件改动）；
- **PR 被要求修改**：直接在你的分支上继续提交即可，PR 会自动更新；合并前建议 `git rebase upstream/main` 保持历史干净。

有任何问题，直接在仓库 Issues 里提，或找仓库主人沟通。
