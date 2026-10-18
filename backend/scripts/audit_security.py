import re
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def audit_requirements(req_path: Path) -> dict:
    """Audit requirements.txt to verify 100% pinned dependency versions."""
    unpinned = []
    pinned = []
    total = 0

    if not req_path.exists():
        return {"status": "error", "message": f"File not found: {req_path}"}

    with open(req_path, "r", encoding="utf-8") as f:
        for line in f:
            clean = line.strip()
            if not clean or clean.startswith("#"):
                continue
            total += 1
            if "==" in clean:
                pinned.append(clean)
            else:
                unpinned.append(clean)

    return {
        "total_dependencies": total,
        "pinned_count": len(pinned),
        "unpinned_count": len(unpinned),
        "unpinned_items": unpinned,
        "is_fully_pinned": len(unpinned) == 0,
    }


def audit_dockerfile(dockerfile_path: Path) -> dict:
    """Audit Dockerfile against security best practices."""
    checks = {
        "multi_stage_build": False,
        "non_root_user": False,
        "no_cache_pip": False,
        "healthcheck_defined": False,
    }

    if not dockerfile_path.exists():
        return {"status": "error", "message": f"Dockerfile not found: {dockerfile_path}"}

    content = dockerfile_path.read_text(encoding="utf-8")
    if "FROM" in content and content.count("FROM") > 1:
        checks["multi_stage_build"] = True
    if re.search(r"^USER\s+(?!root\b)\w+", content, re.MULTILINE):
        checks["non_root_user"] = True
    if "--no-cache-dir" in content:
        checks["no_cache_pip"] = True
    if "HEALTHCHECK" in content:
        checks["healthcheck_defined"] = True

    all_passed = all(checks.values())
    return {
        "checks": checks,
        "passed": all_passed,
    }


def audit_docker_compose(compose_path: Path) -> dict:
    """Audit docker-compose.yml for port isolation and resource limits."""
    if not compose_path.exists():
        return {"status": "error", "message": f"docker-compose.yml not found: {compose_path}"}

    content = compose_path.read_text(encoding="utf-8")
    checks = {
        "no_new_privileges": "no-new-privileges:true" in content,
        "resource_limits": "limits:" in content and "memory:" in content,
        "isolated_ports": "0.0.0.0" not in content and "127.0.0.1:" in content,
        "cap_drop_all": "cap_drop:" in content,
    }

    return {
        "checks": checks,
        "passed": all(checks.values()),
    }


def run_full_security_audit():
    backend_dir = project_root
    req_file = backend_dir / "requirements.txt"
    docker_file = backend_dir / "Dockerfile"
    compose_file = backend_dir / "docker-compose.yml"

    print("=" * 70)
    print("DOCUMIND AI — DEPENDENCY & CONTAINER SECURITY AUDIT")
    print("=" * 70)

    # 1. Dependency pinning audit
    print("\n[1] Dependency Version Pinning Audit:")
    req_report = audit_requirements(req_file)
    print(f"  Total Dependencies: {req_report['total_dependencies']}")
    print(f"  Fully Pinned:       {req_report['pinned_count']}/{req_report['total_dependencies']}")
    if req_report['unpinned_items']:
        print(f"  Unpinned Items:     {req_report['unpinned_items']}")
    else:
        print("  Status:             PASSED (100% Pinned)")

    # 2. Dockerfile audit
    print("\n[2] Dockerfile Security Audit:")
    docker_report = audit_dockerfile(docker_file)
    for check, status in docker_report["checks"].items():
        symbol = "[OK]" if status else "[WARN]"
        print(f"  {symbol} {check}: {status}")
    print(f"  Status:             {'PASSED' if docker_report['passed'] else 'ATTENTION NEEDED'}")

    # 3. Docker Compose audit
    print("\n[3] Container & Port Security Audit:")
    compose_report = audit_docker_compose(compose_file)
    for check, status in compose_report["checks"].items():
        symbol = "[OK]" if status else "[WARN]"
        print(f"  {symbol} {check}: {status}")
    print(f"  Status:             {'PASSED' if compose_report['passed'] else 'ATTENTION NEEDED'}")

    print("\n" + "=" * 70)
    all_ok = req_report["is_fully_pinned"] and docker_report["passed"] and compose_report["passed"]
    print(f"OVERALL AUDIT RESULT: {'SECURE / PASSED' if all_ok else 'ACTION REQUIRED'}")
    print("=" * 70)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(run_full_security_audit())
