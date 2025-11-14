from pyngrok import ngrok

# Deinen Token EINMAL einfügen (du hast ihn schon eingetragen – gut)
ngrok.set_auth_token("34nM44gqGLNshXQyL8EFxHuQsNB_46ReZdxEbnYL9i68X2FvP")

# Öffnet Tunnel zu Port 5000 (wo Flask läuft)
public_url = ngrok.connect(5000)
print("✅ Public URL:", public_url)
input("Drücke ENTER zum Beenden...")
