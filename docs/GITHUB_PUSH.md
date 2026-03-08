# Enviar o projeto para o GitHub

O repositório já está inicializado com um commit. Para enviar para o GitHub:

## 1. Criar um repositório no GitHub

1. Acesse [github.com/new](https://github.com/new).
2. Nome do repositório: por exemplo `courses-advisor`.
3. **Não** marque "Add a README" (o projeto já tem conteúdo).
4. Clique em **Create repository**.

## 2. Conectar o repositório local ao GitHub

No terminal, na pasta do projeto:

```bash
git remote add origin https://github.com/SEU_USUARIO/courses-advisor.git
```

Substitua `SEU_USUARIO` pelo seu usuário do GitHub. Se o repositório tiver outro nome, use esse nome no lugar de `courses-advisor`.

## 3. Enviar o código

```bash
git push -u origin main
```

Se pedir autenticação, use um **Personal Access Token** (não a senha da conta) ou configure SSH.

Depois disso, os próximos envios podem ser feitos apenas com:

```bash
git push
```
