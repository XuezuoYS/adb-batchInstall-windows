
### 操作前

你需要严谨按照要求和约束，若你对于任意问题不确定、未知或拿不准，认为我的要求模糊的，请先向我提问后得到准确回答后再进行。

### 环境

此项目主要使用 `python` 进行编写，并使用 `uv` 作为包管理器，创建虚拟环境，运行脚本，请直接使用：

```
uv run yourWantToRun.py
```

同样，添加、检查三方库安装情况和 Python 版本，请同样使用 `uv` 指令。

### 命名风格

此项目命名风格将使用：对于函数名、变量名、文件名，默认使用小驼峰 `camelCase` 命名，对于类名，默认使用大驼峰 `PascalCase` 命名，对于特殊全局变量，使用全大写`UPPER_CASE` 命名。

### 注释风格

此项目注释风格将使用 `reStructuredText` 风格进行函数和类的注释，如：

```python
async def drawProp(request: Request, line: int):
    """
    道具卡面渲染路由。

    从 prop.xlsx 读取道具数据，拼合背景、图标、牌效、台词等元素，
    并处理左上角费用（支持数字重复和【内容】标记两种格式）。

    :param request: FastAPI 请求对象
    :type request: Request
    :param line: xlsx 中的行号（第 1 行为表头，实际数据从第 2 行开始）
    :type line: int
    :return: 渲染后的 prop.html 页面，或状态码 201/404 的跳过/结束标记
    :rtype: HTMLResponse
    """
    pass # other codes
```

