#!/usr/bin/env python3
"""
BlindOracle Agent Passport Generator v2.0
Generates cryptographically signed, tamper-proof trust documents for agents.

4-Layer Trust:
  1. Schnorr-signed JSON (Nostr Kind 30025)
  2. Rendered PNG passport card (800x1200 via Pillow)
  3. Standalone verifier (separate script)
  4. ZK selective disclosure (Midnight placeholder)

Data Sources (all local, no submodule deps):
  - .claude/agents/*.md  -> agent roster (name, description, tools, model)
  - data/proofs.db       -> proof counts, quality (if exists)
  - .env                 -> BLINDORACLE_HUB_PRIVKEY for signing

Usage:
  python3 scripts/agent_passport_generator.py --agent X --level full
  python3 scripts/agent_passport_generator.py --all --level limited
  python3 scripts/agent_passport_generator.py --list
  python3 scripts/agent_passport_generator.py --team finance

Copyright (c) 2025-2026 BlindOracle. All rights reserved.
"""

import argparse
import hashlib
import json
import logging
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = PROJECT_ROOT / ".claude" / "agents"
PASSPORTS_DIR = PROJECT_ROOT / "data" / "passports"
PROOFS_DB_PATH = PROJECT_ROOT / "data" / "proofs.db"

# Nostr relays for publishing
NOSTR_RELAYS = [
    "wss://relay.damus.io",
    "wss://nos.lol",
    "wss://relay.nostr.band",
]

# Badge thresholds
BADGE_THRESHOLDS = {"gold": 85, "silver": 70, "bronze": 50, "none": 0}

# Team assignments (agent name prefix -> team)
TEAM_MAP = {
    "crypto-": "finance",
    "macro-crypto-": "finance",
    "financial-": "finance",
    "payment-": "finance",
    "x402-": "finance",
    "topic-": "research",
    "tra-": "research",
    "intelligence-": "research",
    "nano-agent-": "nano",
    "ditd-": "ditd",
    "gdr-": "ditd",
    "paypal-": "commerce",
    "security-": "security",
    "vuln-": "security",
    "red-team-": "security",
    "compliance-": "security",
    "discovery-": "security",
    "debate-": "debate",
    "persona-": "debate",
    "reasoning-": "debate",
    "builder-": "dev",
    "debugger-": "dev",
    "tester-": "dev",
    "validator-": "dev",
    "monitor-": "ops",
    "architecture-": "ops",
    "cost-": "ops",
    "system-": "ops",
}

# Tier assignments
TIER_MAP = {
    "security-orchestrator": (1, "blocked"),
    "vuln-assessor": (1, "blocked"),
    "red-team-simulator": (1, "blocked"),
}


def _get_team(agent_name: str) -> str:
    """Derive team from agent name prefix."""
    for prefix, team in TEAM_MAP.items():
        if agent_name.startswith(prefix):
            return team
    return "general"


def _get_tier(agent_name: str) -> Tuple[int, str]:
    """Get agent tier (1=blocked, 2=local, 3=publish)."""
    if agent_name in TIER_MAP:
        return TIER_MAP[agent_name]
    if agent_name.startswith("nano-agent-"):
        return (3, "publish")
    return (2, "local")


def _compute_badge(score: float) -> str:
    """Compute badge from reputation score."""
    if score >= BADGE_THRESHOLDS["gold"]:
        return "gold"
    elif score >= BADGE_THRESHOLDS["silver"]:
        return "silver"
    elif score >= BADGE_THRESHOLDS["bronze"]:
        return "bronze"
    return "none"


# ---------------------------------------------------------------------------
# Agent Discovery
# ---------------------------------------------------------------------------
def discover_agents() -> List[Dict[str, Any]]:
    """Discover all agents from .claude/agents/*.md files."""
    agents = []
    if not AGENTS_DIR.exists():
        logger.warning(f"Agents directory not found: {AGENTS_DIR}")
        return agents

    for md_file in sorted(AGENTS_DIR.glob("*.md")):
        agent = _parse_agent_md(md_file)
        if agent:
            agents.append(agent)
    return agents


def _parse_agent_md(path: Path) -> Optional[Dict[str, Any]]:
    """Parse agent .md file with YAML frontmatter."""
    try:
        content = path.read_text(encoding="utf-8")
        # Extract YAML frontmatter between --- markers
        match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if not match:
            return None

        frontmatter = match.group(1)
        agent = {"source_file": str(path)}

        for line in frontmatter.strip().split("\n"):
            if ":" in line:
                key, _, value = line.partition(":")
                agent[key.strip()] = value.strip()

        if "name" not in agent:
            agent["name"] = path.stem

        # Derive team and tier
        name = agent["name"]
        agent["team"] = _get_team(name)
        tier_num, tier_name = _get_tier(name)
        agent["tier"] = tier_num
        agent["tier_name"] = tier_name

        return agent
    except Exception as e:
        logger.warning(f"Failed to parse {path.name}: {e}")
        return None


# ---------------------------------------------------------------------------
# Proof DB Reader (optional - graceful if missing)
# ---------------------------------------------------------------------------
def _get_proof_stats(agent_name: str) -> Dict[str, Any]:
    """Read proof statistics from data/proofs.db if it exists."""
    result = {
        "total_proofs": 0,
        "published_nostr": 0,
        "unpublished": 0,
        "distinct_kinds": 0,
        "by_kind": {},
        "avg_quality_score": 0.0,
        "total_chains": 0,
        "first_seen": "",
        "last_active": "",
    }

    if not PROOFS_DB_PATH.exists() or PROOFS_DB_PATH.stat().st_size == 0:
        return result

    try:
        conn = sqlite3.connect(str(PROOFS_DB_PATH))
        c = conn.cursor()

        # Check if proofs table exists
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='proofs'")
        if not c.fetchone():
            conn.close()
            return result

        # Total proofs
        row = c.execute(
            "SELECT COUNT(*) FROM proofs WHERE agent_name = ?", (agent_name,)
        ).fetchone()
        result["total_proofs"] = row[0] if row else 0

        if result["total_proofs"] > 0:
            # Published count
            row = c.execute(
                "SELECT COUNT(*) FROM proofs WHERE agent_name = ? AND nostr_published = 1",
                (agent_name,),
            ).fetchone()
            result["published_nostr"] = row[0] if row else 0
            result["unpublished"] = result["total_proofs"] - result["published_nostr"]

            # By kind
            rows = c.execute(
                """SELECT kind, kind_name, COUNT(*) as cnt
                   FROM proofs WHERE agent_name = ?
                   GROUP BY kind ORDER BY cnt DESC""",
                (agent_name,),
            ).fetchall()
            result["by_kind"] = {
                (r[1] or f"Kind_{r[0]}"): {"kind": r[0], "count": r[2]} for r in rows
            }
            result["distinct_kinds"] = len(rows)

            # Quality
            row = c.execute(
                "SELECT AVG(quality_score) FROM proofs WHERE agent_name = ? AND quality_score > 0",
                (agent_name,),
            ).fetchone()
            result["avg_quality_score"] = round(row[0], 3) if row and row[0] else 0.0

            # Chains
            row = c.execute(
                "SELECT COUNT(DISTINCT chain_id) FROM proofs WHERE agent_name = ?",
                (agent_name,),
            ).fetchone()
            result["total_chains"] = row[0] if row else 0

            # First/last
            row = c.execute(
                "SELECT MIN(created_at), MAX(created_at) FROM proofs WHERE agent_name = ?",
                (agent_name,),
            ).fetchone()
            if row:
                result["first_seen"] = row[0] or ""
                result["last_active"] = row[1] or ""

        conn.close()
    except Exception as e:
        logger.warning(f"Proof DB read failed for {agent_name}: {e}")

    return result


# ---------------------------------------------------------------------------
# Reputation Calculator
# ---------------------------------------------------------------------------
def _compute_reputation(proof_stats: Dict) -> Dict[str, Any]:
    """Compute reputation score from proof statistics."""
    total = proof_stats.get("total_proofs", 0)
    quality = proof_stats.get("avg_quality_score", 0.0)
    kinds = proof_stats.get("distinct_kinds", 0)
    chains = proof_stats.get("total_chains", 0)

    # Score formula: weighted combination
    # - Proof volume (0-30 points): log scale, max at 100+ proofs
    import math

    volume_score = min(30, (math.log10(max(total, 1)) / math.log10(100)) * 30)
    # - Quality (0-40 points): direct from avg quality
    quality_score = quality * 40 if quality > 0 else 0
    # - Diversity (0-15 points): distinct kinds, max at 10
    diversity_score = min(15, (kinds / 10) * 15)
    # - Chain depth (0-15 points): chains, max at 20
    chain_score = min(15, (chains / 20) * 15)

    total_score = round(volume_score + quality_score + diversity_score + chain_score, 1)
    total_score = min(100, total_score)  # Cap at 100

    badge = _compute_badge(total_score)

    return {
        "score": total_score,
        "badge": badge,
        "volume_score": round(volume_score, 1),
        "quality_score": round(quality_score, 1),
        "diversity_score": round(diversity_score, 1),
        "chain_score": round(chain_score, 1),
    }


# ---------------------------------------------------------------------------
# Schnorr Signing (BIP-340 via coincurve)
# ---------------------------------------------------------------------------
def _sign_passport(passport_hash: str, privkey_hex: str) -> str:
    """Sign passport hash with Schnorr BIP-340."""
    try:
        from coincurve import PrivateKey

        sk = PrivateKey(bytes.fromhex(privkey_hex))
        msg = bytes.fromhex(passport_hash)
        sig = sk.sign_schnorr(msg)
        return sig.hex()
    except ImportError:
        logger.warning("coincurve not installed - passport unsigned")
        return f"unsigned:no_coincurve"
    except Exception as e:
        logger.warning(f"Signing failed: {e}")
        return f"unsigned:{e}"


def _get_hub_pubkey(privkey_hex: str) -> str:
    """Derive public key from private key."""
    try:
        from coincurve import PrivateKey

        sk = PrivateKey(bytes.fromhex(privkey_hex))
        pk = sk.public_key
        # x-only pubkey (32 bytes) for BIP-340
        return pk.format(compressed=True)[1:].hex()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Passport Generator Class
# ---------------------------------------------------------------------------
class AgentPassportGenerator:
    """Generate a cryptographically signed agent passport."""

    def __init__(self, agent_info: Dict[str, Any], level: str = "limited"):
        self.agent_info = agent_info
        self.agent_name = agent_info["name"]
        self.level = level  # "limited" or "full"
        self.hub_privkey = os.environ.get("BLINDORACLE_HUB_PRIVKEY", "")

    def generate(self) -> Dict[str, Any]:
        """Generate complete passport document."""
        now = datetime.now(timezone.utc).isoformat()

        # Collect data
        proof_stats = _get_proof_stats(self.agent_name)
        reputation = _compute_reputation(proof_stats)

        # Build passport
        passport = {
            "passport_version": "2.0.0",
            "validation_level": self.level,
            "generated_at": now,
            "issuer": {
                "name": "BlindOracle Hub (ConsensusKing)",
                "relays": NOSTR_RELAYS,
            },
            "identity": {
                "agent_name": self.agent_name,
                "description": self.agent_info.get("description", ""),
                "team": self.agent_info.get("team", "general"),
                "tier": self.agent_info.get("tier", 2),
                "tier_name": self.agent_info.get("tier_name", "local"),
                "model": self.agent_info.get("model", ""),
                "tools": self.agent_info.get("tools", ""),
                "status": "active",
            },
            "reputation": reputation,
            "proof_summary": proof_stats,
        }

        # Add hub pubkey if available
        if self.hub_privkey:
            pubkey = _get_hub_pubkey(self.hub_privkey)
            passport["issuer"]["hub_pubkey"] = pubkey

        # Compute hash
        canonical = json.dumps(passport, sort_keys=True, separators=(",", ":"))
        passport_hash = hashlib.sha256(canonical.encode()).hexdigest()
        passport["passport_hash"] = passport_hash

        # Sign
        if self.hub_privkey:
            signature = _sign_passport(passport_hash, self.hub_privkey)
            passport["signature"] = signature
        else:
            passport["signature"] = "unsigned:no_key"

        return passport

    def to_nostr_event(self, passport: Dict) -> Dict:
        """Wrap passport as Nostr Kind 30025 replaceable event."""
        rep = passport.get("reputation", {})
        return {
            "kind": 30025,
            "content": json.dumps(passport),
            "tags": [
                ["d", self.agent_name],
                ["t", "agent-passport"],
                ["t", "blindoracle"],
                ["passport_version", passport.get("passport_version", "2.0.0")],
                ["validation_level", self.level],
                ["passport_hash", passport.get("passport_hash", "")],
                ["reputation_score", str(rep.get("score", 0))],
                ["reputation_badge", rep.get("badge", "none")],
                ["total_proofs", str(passport.get("proof_summary", {}).get("total_proofs", 0))],
                ["r", "https://craigmbrown.com/blindoracle/"],
            ],
        }

    def render_png(self, passport: Dict, output_path: Path) -> bool:
        """Render passport as PNG card (800x1200)."""
        try:
            from PIL import Image, ImageDraw, ImageFont

            W, H = 800, 1200
            # Dark theme colors
            bg = (26, 26, 26)
            card_bg = (45, 45, 45)
            gold_color = (255, 215, 0)
            silver_color = (192, 192, 192)
            bronze_color = (205, 127, 50)
            white = (224, 224, 224)
            blue = (74, 158, 255)
            muted = (128, 128, 128)
            green = (76, 175, 80)

            badge = passport.get("reputation", {}).get("badge", "none")
            badge_colors = {
                "gold": gold_color,
                "silver": silver_color,
                "bronze": bronze_color,
                "none": muted,
            }
            accent = badge_colors.get(badge, muted)

            img = Image.new("RGB", (W, H), bg)
            draw = ImageDraw.Draw(img)

            # Try to load fonts, fall back to default
            try:
                title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
                body_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
                small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
                mono_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 14)
            except (IOError, OSError):
                title_font = ImageFont.load_default()
                body_font = title_font
                small_font = title_font
                mono_font = title_font

            # Card background with rounded corners effect
            draw.rectangle([(30, 30), (W - 30, H - 30)], fill=card_bg)
            # Top accent bar
            draw.rectangle([(30, 30), (W - 30, 38)], fill=accent)

            y = 60

            # Title
            draw.text((50, y), "BLINDORACLE AGENT PASSPORT", fill=accent, font=title_font)
            y += 45
            draw.line([(50, y), (W - 50, y)], fill=accent, width=2)
            y += 25

            # Identity section
            identity = passport.get("identity", {})
            draw.text((50, y), f"Agent: {identity.get('agent_name', 'unknown')}", fill=white, font=body_font)
            y += 35

            desc = identity.get("description", "")[:80]
            if desc:
                draw.text((50, y), desc, fill=muted, font=small_font)
                y += 25

            y += 10
            draw.text((50, y), f"Team: {identity.get('team', 'general')}", fill=white, font=body_font)
            draw.text((400, y), f"Tier: {identity.get('tier_name', 'local')}", fill=white, font=body_font)
            y += 30
            draw.text((50, y), f"Model: {identity.get('model', 'N/A')}", fill=muted, font=body_font)
            draw.text((400, y), f"Status: {identity.get('status', 'active').upper()}", fill=green, font=body_font)
            y += 50

            # Reputation box
            rep = passport.get("reputation", {})
            score = rep.get("score", 0)
            badge_text = rep.get("badge", "none").upper()

            draw.rectangle([(50, y), (W - 50, y + 100)], fill=(30, 30, 30), outline=accent)
            draw.text((70, y + 10), f"REPUTATION: {score}/100", fill=white, font=title_font)

            badge_star = {"GOLD": "***", "SILVER": "**", "BRONZE": "*", "NONE": ""}.get(badge_text, "")
            draw.text((70, y + 50), f"{badge_star} {badge_text}", fill=accent, font=body_font)

            # Score breakdown
            draw.text((400, y + 15), f"Volume: {rep.get('volume_score', 0)}", fill=muted, font=small_font)
            draw.text((400, y + 35), f"Quality: {rep.get('quality_score', 0)}", fill=muted, font=small_font)
            draw.text((400, y + 55), f"Diversity: {rep.get('diversity_score', 0)}", fill=muted, font=small_font)
            draw.text((400, y + 75), f"Chains: {rep.get('chain_score', 0)}", fill=muted, font=small_font)
            y += 120

            # Proof summary
            proofs = passport.get("proof_summary", {})
            draw.text((50, y), "PROOF SUMMARY", fill=blue, font=body_font)
            y += 30
            draw.text((50, y), f"Total: {proofs.get('total_proofs', 0)}", fill=white, font=body_font)
            draw.text((250, y), f"Published: {proofs.get('published_nostr', 0)}", fill=white, font=body_font)
            draw.text((500, y), f"Kinds: {proofs.get('distinct_kinds', 0)}", fill=white, font=body_font)
            y += 30
            draw.text((50, y), f"Quality Avg: {proofs.get('avg_quality_score', 0)}", fill=muted, font=body_font)
            draw.text((350, y), f"Chains: {proofs.get('total_chains', 0)}", fill=muted, font=body_font)
            y += 30

            if proofs.get("first_seen"):
                draw.text((50, y), f"Active: {proofs['first_seen'][:10]} - {proofs.get('last_active', '')[:10]}", fill=muted, font=small_font)
                y += 25

            y += 20

            # Proof kinds breakdown (top 5)
            by_kind = proofs.get("by_kind", {})
            if by_kind:
                draw.text((50, y), "PROOF TYPES", fill=blue, font=body_font)
                y += 28
                for i, (kind_name, kind_data) in enumerate(list(by_kind.items())[:5]):
                    draw.text((70, y), f"{kind_name}: {kind_data['count']}", fill=white, font=small_font)
                    y += 22

            y = max(y + 30, 850)

            # Signature section
            draw.line([(50, y), (W - 50, y)], fill=accent, width=1)
            y += 15
            draw.text((50, y), "PASSPORT HASH", fill=blue, font=small_font)
            y += 20
            phash = passport.get("passport_hash", "")
            draw.text((50, y), phash[:40] + "...", fill=muted, font=mono_font)
            y += 20
            draw.text((50, y), phash[40:], fill=muted, font=mono_font)
            y += 30

            sig = passport.get("signature", "")
            sig_status = "SIGNED" if not sig.startswith("unsigned") else "UNSIGNED"
            sig_color = green if sig_status == "SIGNED" else (244, 67, 54)
            draw.text((50, y), f"Signature: {sig_status}", fill=sig_color, font=body_font)
            y += 25
            if sig_status == "SIGNED":
                draw.text((50, y), f"Sig: {sig[:50]}...", fill=muted, font=mono_font)
                y += 20

            draw.text((50, y + 10), f"Issuer: ConsensusKing (BlindOracle Hub)", fill=muted, font=small_font)
            y += 30
            draw.text((50, y + 10), f"Generated: {passport.get('generated_at', '')[:19]}Z", fill=muted, font=small_font)
            y += 30
            draw.text((50, y + 10), f"Level: {passport.get('validation_level', 'limited')}", fill=muted, font=small_font)

            # Footer
            draw.rectangle([(30, H - 60), (W - 30, H - 30)], fill=accent)
            draw.text((50, H - 55), "BlindOracle Agent Passport v2.0", fill=(26, 26, 26), font=body_font)
            draw.text((550, H - 55), "craigmbrown.com", fill=(26, 26, 26), font=small_font)

            img.save(str(output_path), "PNG")
            return True

        except ImportError:
            logger.warning("Pillow not installed - PNG not generated")
            return False
        except Exception as e:
            logger.warning(f"PNG render failed: {e}")
            return False

    def save(self, passport: Dict) -> Tuple[str, str]:
        """Save passport JSON and PNG to data/passports/."""
        PASSPORTS_DIR.mkdir(parents=True, exist_ok=True)

        json_path = PASSPORTS_DIR / f"{self.agent_name}_passport.json"
        png_path = PASSPORTS_DIR / f"{self.agent_name}_passport.png"

        # Save JSON
        with open(json_path, "w") as f:
            json.dump(passport, f, indent=2)

        # Render PNG
        png_ok = self.render_png(passport, png_path)

        return str(json_path), str(png_path) if png_ok else ""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="BlindOracle Agent Passport Generator v2.0")
    parser.add_argument("--agent", help="Generate passport for specific agent")
    parser.add_argument("--all", action="store_true", help="Generate for all agents")
    parser.add_argument("--team", help="Generate for all agents in a team")
    parser.add_argument("--list", action="store_true", help="List all discoverable agents")
    parser.add_argument("--level", default="limited", choices=["limited", "full"],
                        help="Validation level (limited=no signing, full=Schnorr signed)")
    parser.add_argument("--json-only", action="store_true", help="Skip PNG generation")
    args = parser.parse_args()

    agents = discover_agents()
    logger.info(f"Discovered {len(agents)} agents from {AGENTS_DIR}")

    if args.list:
        print(f"\n{'Name':<45} {'Team':<12} {'Tier':<10} {'Model':<10}")
        print("-" * 80)
        for a in agents:
            print(f"{a['name']:<45} {a.get('team',''):<12} {a.get('tier_name',''):<10} {a.get('model',''):<10}")
        print(f"\nTotal: {len(agents)} agents")
        return

    # Filter agents
    targets = []
    if args.agent:
        targets = [a for a in agents if a["name"] == args.agent]
        if not targets:
            logger.error(f"Agent '{args.agent}' not found. Use --list to see available agents.")
            sys.exit(1)
    elif args.team:
        targets = [a for a in agents if a.get("team") == args.team]
        if not targets:
            logger.error(f"No agents found for team '{args.team}'")
            sys.exit(1)
    elif args.all:
        targets = agents
    else:
        parser.print_help()
        return

    logger.info(f"Generating {args.level} passports for {len(targets)} agent(s)\n")

    results = {"success": 0, "failed": 0, "badges": {"gold": 0, "silver": 0, "bronze": 0, "none": 0}}

    for agent in targets:
        name = agent["name"]
        print(f"{'=' * 60}")
        print(f"Generating {args.level} passport for: {name}")
        print(f"{'=' * 60}")

        try:
            gen = AgentPassportGenerator(agent, level=args.level)
            passport = gen.generate()
            json_path, png_path = gen.save(passport)

            rep = passport.get("reputation", {})
            badge = rep.get("badge", "none")
            results["badges"][badge] += 1
            results["success"] += 1

            print(f"  JSON: {json_path}")
            if png_path:
                print(f"  PNG:  {png_path}")
            print(f"  Hash: {passport.get('passport_hash', '')[:30]}...")
            print(f"  Sig:  {passport.get('signature', '')[:30]}...")
            print(f"  Score: {rep.get('score', 0)}")
            print(f"  Badge: {badge}")
            print()

        except Exception as e:
            logger.error(f"Failed for {name}: {e}")
            results["failed"] += 1

    # Summary
    print(f"\n{'=' * 60}")
    print(f"SUMMARY: {results['success']} generated, {results['failed']} failed")
    print(f"Badges: {results['badges']}")
    print(f"Output: {PASSPORTS_DIR}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
