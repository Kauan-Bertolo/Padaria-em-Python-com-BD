import psycopg2
from psycopg2 import sql
import enum

DATABASE_NAME = 'padaria'
USER = 'postgres'
PASSWORD = 'fatec'
HOST = 'localhost'
PORT = '5433'

# Enum para o status do pedido
class PedidoStatus(enum.Enum):
    PENDENTE = "Pendente"
    CONCLUIDO = "Concluído"
    CANCELADO = "Cancelado"

def conectar():
    return psycopg2.connect(dbname=DATABASE_NAME, user=USER, password=PASSWORD, host=HOST, port=PORT)

def adicionar_produto(nome, preco, estoque):
    try:
        conn = conectar()
        with conn.cursor() as cursor:
            # Verificar se há IDs excluídos disponíveis para reutilização
            cursor.execute("SELECT id_excluido FROM ids_excluidos WHERE tipo = %s ORDER BY id LIMIT 1;", ('produto',))
            id_excluido = cursor.fetchone()
            if id_excluido:
                produto_id = id_excluido[0]
                cursor.execute("DELETE FROM ids_excluidos WHERE id_excluido = %s;", (produto_id,))
            else:
                # Obter o próximo ID disponível
                cursor.execute("SELECT nextval('produtos_id_seq');")
                produto_id = cursor.fetchone()[0]

            # Adicionar o novo produto
            cursor.execute(
                "INSERT INTO produtos (id, nome, preco, estoque) VALUES (%s, %s, %s, %s);",
                (produto_id, nome, preco, estoque)
            )
            conn.commit()
            print("Produto adicionado com sucesso.")
    except Exception as e:
        print(f"Erro ao adicionar produto: {e}")
    finally:
        conn.close()
        
def listar_produtos():
    try:
        conn = conectar()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM produtos;")
            produtos = cursor.fetchall()
            for produto in produtos:
                print(f"ID: {produto[0]}, Nome: {produto[1]}, Preço: {produto[2]}, Estoque: {produto[3]}")
    except Exception as e:
        print(f"Erro ao listar produtos: {e}")
    finally:
        conn.close()

def limpar_ids_excluidos():
    try:
        conn = conectar()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM ids_excluidos WHERE tipo = %s;", ('produto',))
            conn.commit()
            print("IDs excluídos limpos com sucesso.")
    except Exception as e:
        print(f"Erro ao limpar IDs excluídos: {e}")
    finally:
        conn.close()

def excluir_produto(produto_id):
    try:
        conn = conectar()
        with conn.cursor() as cursor:
            # Verificar se o produto existe
            cursor.execute("SELECT nome FROM produtos WHERE id = %s;", (produto_id,))
            produto = cursor.fetchone()
            if produto is None:
                print("Produto não encontrado.")
                return

            # Verificar se o produto está referenciado em pedidos
            cursor.execute("SELECT COUNT(*) FROM pedidos WHERE produto_id = %s;", (produto_id,))
            referenciado = cursor.fetchone()[0]

            if referenciado > 0:
                print(f"Produto '{produto[0]}' está referenciado em {referenciado} pedido(s).")
                print("Para excluir este produto, você precisa remover ou atualizar os pedidos associados.")
                return

            # Excluir o produto
            cursor.execute("DELETE FROM produtos WHERE id = %s;", (produto_id,))
            conn.commit()
            print(f"Produto '{produto[0]}' excluído com sucesso.")
    except Exception as e:
        print(f"Erro ao excluir produto: {e}")
    finally:
        conn.close()

def criar_pedido(cliente_nome, produtos_quantidades):
    try:
        conn = conectar()
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO pedidos (cliente_nome, status) VALUES (%s, %s) RETURNING id;",
                (cliente_nome, PedidoStatus.PENDENTE.value)
            )
            pedido_id = cursor.fetchone()[0]

            for produto_id, quantidade in produtos_quantidades:
                cursor.execute("SELECT estoque FROM produtos WHERE id = %s;", (produto_id,))
                produto = cursor.fetchone()
                if produto is None:
                    print(f"Produto com ID {produto_id} não encontrado.")
                    continue
                
                estoque_atual = produto[0]
                if estoque_atual < quantidade:
                    print(f"Estoque insuficiente para o produto com ID {produto_id}.")
                    continue
                
                cursor.execute(
                    "INSERT INTO itens_pedido (pedido_id, produto_id, quantidade) VALUES (%s, %s, %s);",
                    (pedido_id, produto_id, quantidade)
                )
                cursor.execute(
                    "UPDATE produtos SET estoque = estoque - %s WHERE id = %s;",
                    (quantidade, produto_id)
                )
            conn.commit()
            print("Pedido criado com sucesso.")
    except Exception as e:
        print(f"Erro ao criar pedido: {e}")
    finally:
        conn.close()

def listar_pedidos():
    try:
        conn = conectar()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT p.id, p.cliente_nome, pr.nome, ip.quantidade, p.status, p.data_criacao "
                "FROM pedidos p "
                "JOIN itens_pedido ip ON p.id = ip.pedido_id "
                "JOIN produtos pr ON ip.produto_id = pr.id;"
            )
            pedidos = cursor.fetchall()
            for pedido in pedidos:
                print(f"ID: {pedido[0]}, Cliente: {pedido[1]}, Produto: {pedido[2]}, Quantidade: {pedido[3]}, Status: {pedido[4]}, Data: {pedido[5]}")
    except Exception as e:
        print(f"Erro ao listar pedidos: {e}")
    finally:
        conn.close()

def atualizar_status_pedido(pedido_id, novo_status):
    try:
        conn = conectar()
        with conn.cursor() as cursor:
            try:
                status_enum = PedidoStatus[novo_status.upper()]
            except KeyError:
                print("Status inválido.")
                return
            
            cursor.execute(
                "UPDATE pedidos SET status = %s WHERE id = %s;",
                (status_enum.value, pedido_id)
            )
            
            if status_enum == PedidoStatus.CANCELADO:
                cursor.execute(
                    "SELECT produto_id, quantidade FROM itens_pedido WHERE pedido_id = %s;",
                    (pedido_id,)
                )
                itens = cursor.fetchall()
                
                for produto_id, quantidade in itens:
                    cursor.execute(
                        "UPDATE produtos SET estoque = estoque + %s WHERE id = %s;",
                        (quantidade, produto_id)
                    )
                
            conn.commit()
            print(f"Status do pedido atualizado para '{status_enum.value}'.")
    except Exception as e:
        print(f"Erro ao atualizar status do pedido: {e}")
    finally:
        conn.close()

def excluir_pedido(pedido_id):
    try:
        conn = conectar()
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM pedidos WHERE id = %s;", (pedido_id,))
            pedido = cursor.fetchone()
            if pedido is None:
                print("Pedido não encontrado.")
                return

            cursor.execute("SELECT produto_id, quantidade FROM itens_pedido WHERE pedido_id = %s;", (pedido_id,))
            itens = cursor.fetchall()

            cursor.execute("DELETE FROM pedidos WHERE id = %s;", (pedido_id,))
            for produto_id, quantidade in itens:
                cursor.execute(
                    "UPDATE produtos SET estoque = estoque + %s WHERE id = %s;",
                    (quantidade, produto_id)
                )
            conn.commit()
            print(f"Pedido {pedido_id} excluído com sucesso.")
    except Exception as e:
        print(f"Erro ao excluir pedido: {e}")
    finally:
        conn.close()

def menu():
    while True:
        print("\nMenu:")
        print("1. Adicionar produto")
        print("2. Listar produtos")
        print("3. Excluir produto")
        print("4. Criar pedido")
        print("5. Listar pedidos")
        print("6. Atualizar status do pedido")
        print("7. Excluir pedido")
        print("8. Sair")
        
        opcao = input("Escolha uma opção: ")
        
        if opcao == '1':
            nome = input("Nome do produto: ")
            preco = float(input("Preço do produto: "))
            estoque = int(input("Estoque do produto: "))
            adicionar_produto(nome, preco, estoque)
        elif opcao == '2':
            listar_produtos()
        elif opcao == '3':
            produto_id = int(input("ID do produto a ser excluído: "))
            excluir_produto(produto_id)
        elif opcao == '4':
            cliente_nome = input("Nome do cliente: ")
            produtos_quantidades = []
            while True:
                produto_id = int(input("ID do produto (ou 0 para terminar): "))
                if produto_id == 0:
                    break
                quantidade = int(input("Quantidade: "))
                produtos_quantidades.append((produto_id, quantidade))
            criar_pedido(cliente_nome, produtos_quantidades)
        elif opcao == '5':
            listar_pedidos()
        elif opcao == '6':
            pedido_id = int(input("ID do pedido: "))
            novo_status = input("Novo status (Pendente, Concluído, Cancelado): ")
            atualizar_status_pedido(pedido_id, novo_status)
        elif opcao == '7':
            pedido_id = int(input("ID do pedido a ser excluído: "))
            excluir_pedido(pedido_id)
        elif opcao == '8':
            break
        else:
            print("Opção inválida, por favor escolha uma opção válida.")

if __name__ == "__main__":
    menu()
