run-all base_url model dir="" max_context="0":
    python run_all_policies.py {{base_url}} {{model}} {{ if dir != "" { "-d " + dir } else { "" } }} --max-context {{max_context}}
