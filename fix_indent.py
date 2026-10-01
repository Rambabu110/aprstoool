with open('web/app.py', 'rb') as f:
    content = f.read()

# Fix: body of try: should be at 24 spaces, except: at 20 spaces
old1 = b'                    try:\r\n                    usage_result = svc.consume_feature_usage(user["user_id"], "swarm_scan")\r\n                    st.session_state["usage_status"] = svc.check_usage(user["user_id"])\r\n                    st.success(f"\xe2\x9c\x85 Usage consumed ({usage_result[\'usage_type\']}). {usage_result.ge\r\n                except Exception as e:'
new1 = b'                    try:\r\n                        usage_result = svc.consume_feature_usage(user["user_id"], "swarm_scan")\r\n                        st.session_state["usage_status"] = svc.check_usage(user["user_id"])\r\n                        st.success(f"\xe2\x9c\x85 Usage consumed ({usage_result[\'usage_type\']}). {usage_result.ge\r\n                except Exception as e:'

content = content.replace(old1, new1)

with open('web/app.py', 'wb') as f:
    f.write(content)
print('Fixed')