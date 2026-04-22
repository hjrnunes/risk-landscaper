run-battery battery base_url model="" max_context="":
    python run_all_policies.py {{battery}} --base-url {{base_url}} {{ if model != "" { "--model " + model } else { "" } }} {{ if max_context != "" { "--max-context " + max_context } else { "" } }}

run-standard base_url model="" max_context="":
    just run-battery batteries/standard.yaml {{base_url}} {{model}} {{max_context}}

run-frontier base_url model="" max_context="":
    just run-battery batteries/frontier.yaml {{base_url}} {{model}} {{max_context}}
