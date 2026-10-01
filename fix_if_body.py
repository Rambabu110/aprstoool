with open('web/app.py', 'rb') as f:
    content = f.read()

# Fix: body of if at 24 spaces should be at 28 spaces
old = b'                        if "USAGE_LIMIT_REACHED" in str(e):\r\n                        st.error("\xf0\x9f\x9a\xab Weekly limit reached! Upgrade your plan to continue.")\r\n                        st.session_state["show_pricing"] = True\r\n                        st.rerun()\r\n                        else:'
new = b'                        if "USAGE_LIMIT_REACHED" in str(e):\r\n                            st.error("\xf0\x9f\x9a\xab Weekly limit reached! Upgrade your plan to continue.")\r\n                            st.session_state["show_pricing"] = True\r\n                            st.rerun()\r\n                        else:'

content = content.replace(old, new)

with open('web/app.py', 'wb') as f:
    f.write(content)
print('Fixed')