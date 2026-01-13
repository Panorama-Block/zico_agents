#!/usr/bin/env python3
"""
CLI para testar o Zico Agents.

Uso:
    python chat_cli.py

Para remover depois, basta deletar este arquivo.
"""

import argparse
import json
import sys
import httpx
from datetime import datetime

# Configuração
BASE_URL = "http://localhost:8000"
USER_ID = "cli-tester"
CONVERSATION_ID = f"cli-session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


class Colors:
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    END = "\033[0m"


def print_header():
    print(f"\n{Colors.CYAN}{Colors.BOLD}╔══════════════════════════════════════════════════════════╗{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}║            ZICO AGENTS - CLI TESTER                      ║{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}╚══════════════════════════════════════════════════════════╝{Colors.END}")
    print(f"{Colors.YELLOW}User: {USER_ID} | Session: {CONVERSATION_ID}{Colors.END}")
    print(f"{Colors.YELLOW}Comandos: 'sair' para sair | 'custos' para ver custos | 'limpar' para nova sessão{Colors.END}")
    print()


def check_server():
    try:
        response = httpx.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print(f"{Colors.GREEN}[OK] Servidor conectado{Colors.END}")
            return True
    except httpx.ConnectError:
        print(f"{Colors.RED}[ERRO] Servidor não encontrado em {BASE_URL}{Colors.END}")
        print(f"{Colors.YELLOW}Rode primeiro: uvicorn src.app:app --reload --port 8000{Colors.END}")
        return False
    except Exception as e:
        print(f"{Colors.RED}[ERRO] {e}{Colors.END}")
        return False


def show_models():
    try:
        response = httpx.get(f"{BASE_URL}/models", timeout=10)
        data = response.json()
        print(f"\n{Colors.CYAN}Modelos disponíveis:{Colors.END}")
        print(f"  Default: {Colors.GREEN}{data.get('default')}{Colors.END}")
        print(f"  Providers: {', '.join(data.get('providers', []))}")
    except Exception as e:
        print(f"{Colors.RED}Erro ao buscar modelos: {e}{Colors.END}")


def show_costs():
    try:
        response = httpx.get(f"{BASE_URL}/costs", timeout=10)
        data = response.json()
        print(f"\n{Colors.CYAN}═══ Custos LLM ═══{Colors.END}")
        print(f"  Total: {Colors.GREEN}${data.get('total_cost', 0):.6f}{Colors.END}")
        tokens = data.get('total_tokens', {})
        print(f"  Tokens: {tokens.get('input', 0):,} in / {tokens.get('output', 0):,} out")
        print(f"  Chamadas: {data.get('calls_count', 0)}")
        print()
    except Exception as e:
        print(f"{Colors.RED}Erro ao buscar custos: {e}{Colors.END}")


def chat(message: str, conversation_id: str) -> str:
    """Envia mensagem e recebe resposta."""
    payload = {
        "message": {
            "role": "user",
            "content": message
        },
        "user_id": USER_ID,
        "conversation_id": conversation_id,
        "wallet_address": "default"
    }

    try:
        print(f"{Colors.YELLOW}Aguardando resposta...{Colors.END}", end="\r")
        response = httpx.post(
            f"{BASE_URL}/chat",
            json=payload,
            timeout=120
        )

        if response.status_code == 200:
            data = response.json()
            return data.get("response", "Sem resposta")
        else:
            return f"Erro {response.status_code}: {response.text}"

    except httpx.TimeoutException:
        return "Timeout - resposta demorou muito"
    except Exception as e:
        return f"Erro: {e}"


def main():
    global BASE_URL, CONVERSATION_ID

    parser = argparse.ArgumentParser(description="CLI para testar Zico Agents")
    parser.add_argument("--url", default="http://localhost:8000", help="URL do servidor")
    args = parser.parse_args()

    BASE_URL = args.url

    print_header()

    if not check_server():
        sys.exit(1)

    show_models()

    print(f"\n{Colors.CYAN}{'─' * 60}{Colors.END}\n")

    while True:
        try:
            user_input = input(f"{Colors.BLUE}Você:{Colors.END} ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["sair", "exit", "quit", "q"]:
                print(f"\n{Colors.YELLOW}Até mais!{Colors.END}")
                show_costs()
                break

            if user_input.lower() == "custos":
                show_costs()
                continue

            if user_input.lower() == "limpar":
                CONVERSATION_ID = f"cli-session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                print(f"{Colors.YELLOW}Nova sessão: {CONVERSATION_ID}{Colors.END}\n")
                continue

            if user_input.lower() == "modelos":
                show_models()
                continue

            response = chat(user_input, CONVERSATION_ID)
            print(f"{Colors.GREEN}Zico:{Colors.END} {response}")
            print()

        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}Interrompido. Até mais!{Colors.END}")
            show_costs()
            break
        except EOFError:
            break


if __name__ == "__main__":
    main()
