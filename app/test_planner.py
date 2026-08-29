from app.planner import create_plan
from app.validator import validate_plan


request = input("LocalOps> ")

try:

    plan = create_plan(request)

    commands = validate_plan(plan)

except (ValueError, RuntimeError) as error:

    print("\nPLAN REJECTED")
    print(error)

    raise SystemExit(1)


print("\n─────────────────────────────────────")
print("PLAN")
print("─────────────────────────────────────")

print("\nProblem:")
print(plan["problem"])

print("\nAssessment:")
print(plan["assessment"])

print(f"\nWorkflow: {plan['workflow_id']}")

print("\nCommands:")

for index, item in enumerate(commands, 1):

    print(f"\n{index}. $ {item['command']}")
    print(f"   What: {item['description']}")
    print(f"   Why:  {item['purpose']}")
    print(f"   Risk: {item['risk']}")
    print(f"   Read-only: {item['read_only']}")

print("\n─────────────────────────────────────")
print("PLAN VALIDATED")
print("No commands have been executed.")
print("─────────────────────────────────────")
