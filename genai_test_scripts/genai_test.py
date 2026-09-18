import asyncio
import time
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from google import genai

# 配置参数
GITHUB_TOKEN = ""
REPO_OWNER = "jiachengpizza-boop"
REPO_NAME = "genai_monitor_test"
GEMINI_API_KEY = ""

client = genai.Client(api_key=GEMINI_API_KEY)

async def main():
    # 1. 配置并启动 GitHub MCP Server 子进程 (通过 npx)
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        env={"GITHUB_PERSONAL_ACCESS_TOKEN": GITHUB_TOKEN}
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # 初始化 MCP 会话
            await session.initialize()
            print("GitHub MCP Server 连接成功！")

            processed_shas = set()

            # 初始化：获取已有 Commit 列表
            init_res = await session.call_tool(
                "list_commits",
                arguments={"owner": REPO_OWNER, "repo": REPO_NAME}
            )
            # init_res 包含结构化的 commit 列表数据，此处记录初始 SHA
            # （假设解析逻辑已封装）

            while True:
                try:
                    # 2. 通过 MCP 工具轮询最新 Commit
                    commits_res = await session.call_tool(
                        "list_commits",
                        arguments={"owner": REPO_OWNER, "repo": REPO_NAME}
                    )
                    
                    # 假设解析得到 new_commits 列表
                    new_commits = [] # 过滤未处理的 commit...

                    # 3. 满足触发条件 N >= 3
                    if len(new_commits) >= 3:
                        print(f"MCP 检测到 {len(new_commits)} 笔新提交，提取 Diff...")
                        
                        diff_text_list = []
                        for c in new_commits:
                            # 通过 MCP 工具获取详细变更
                            commit_detail = await session.call_tool(
                                "get_commit",
                                arguments={"owner": REPO_OWNER, "repo": REPO_NAME, "ref": c['sha']}
                            )
                            diff_text_list.append(str(commit_detail))

                        # 4. 提交给 Gemini 生成 Code Review
                        prompt = f"请审查以下代码变更：\n\n" + "\n\n".join(diff_text_list)
                        response = client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=prompt
                        )

                        # 5. 通过 MCP 工具写回 Review Comment
                        latest_sha = new_commits[0]['sha']
                        await session.call_tool(
                            "create_issue_comment", # 或使用 commit comment 相关 MCP 工具
                            arguments={
                                "owner": REPO_OWNER,
                                "repo": REPO_NAME,
                                "body": f"🤖 **Gemini MCP Code Review**\n\n{response.text}"
                            }
                        )
                        print("Review 已通过 MCP 成功提交！")

                except Exception as e:
                    print(f"MCP 轮询异常: {e}")

                await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())