with open('web/app.py', 'rb') as f:
    content = f.read()

# Fix: else body should be at 28 spaces
old = b'                        else:\r\n                        st.error(f"Usage check failed: {e}")\r\n                        st.stop()'
new = b'                        else:\r\n                            st.error(f"Usage check failed: {e}")\r\n                            st.stop()'

content = content.replace(old, new)

with open('web/app.py', 'wb') as f:
    f.write(content)
print('Fixed')