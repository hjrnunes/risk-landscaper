run-all base_url model:
    python run_all_policies.py {{base_url}} {{model}}

run-frontier base_url model max_context="0":
    python run_all_policies.py {{base_url}} {{model}} -d frontier_safety --max-context {{max_context}}
