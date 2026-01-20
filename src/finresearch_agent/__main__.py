# 提供通过 `python -m finresearch_agent` 运行时的模块入口，将调用转发到 CLI 主函数 main。
from finresearch_agent.cli import main

if __name__ == "__main__":
    main()
