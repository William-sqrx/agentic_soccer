# Cloning a Private GitHub Repository on EC2

For secure cloning of private repositories to your EC2 instance, follow these steps.

## Setting Up Deploy Keys (Recommended)
Deploy keys are ideal for deployment scenarios as they provide read-only access to a single repository.

### Step 1: Generate a New SSH Key Pair
1. SSH into your EC2 instance.
2. Generate an SSH key pair using the following command:
   ```bash
   ssh-keygen -t ed25519 -C "deploy-key-your-repo"
   ```
3. When prompted, save the key pair (e.g., `/home/ec2-user/.ssh/id_ed25519_github`). Leave the passphrase empty.
4. Copy the public key:
   ```bash
   cat /home/ec2-user/.ssh/id_ed25519_github.pub
   ```

### Step 2: Add Deploy Key to GitHub
1. Go to your repository on GitHub.
2. Navigate to **Settings** > **Deploy keys**.
3. Click **Add deploy key**.
4. Paste the public key from the EC2 instance.
5. Ensure **Allow write access** is **unchecked** (read-only).
6. Save the deploy key.

### Step 3: Test the SSH Connection
1. On the EC2 instance, test the SSH connection:
   ```bash
   ssh -T -i /home/ec2-user/.ssh/id_ed25519_github git@github.com
   ```
2. If successful, you will see a message like:
   ```
   Hi username! You've successfully authenticated, but GitHub does not provide shell access.
   ```

### Step 4: Clone the Repository
Use the SSH URL to clone:
```bash
git clone git@github.com:your-username/your-repo.git
```

---

## Alternative: Using a Personal Access Token (PAT)

If you prefer HTTPS cloning using a GitHub Personal Access Token:

1. Generate a PAT:
   1. Go to **Settings** > **Developer settings** > **Personal access tokens** > **Tokens (classic)**.
   2. Generate a token with `read:repo` scope.

2. Configure Git to cache the PAT securely:
   ```bash
   git config --global credential.helper cache
   ```

3. Clone with the token:
   ```bash
   git clone https://<your-username>:<your-token>@github.com/your-username/your-repo.git
   ```

> **Note:** Replace `<your-token>` with the generated token. Avoid leaving tokens in scripts or logs.

---

For deployment-specific scenarios, deploy keys are recommended to ensure minimal and specific access control.

