import shutil, os, yaml

bak = r'g:\dev\ha\ha\backup_10_printer_20260511_060303.yaml'
src = r'\\192.168.0.130\config\automations\10_printer.yaml'

shutil.copy2(bak, src)
print(f'RESTORED from backup: {os.path.getsize(src)} bytes')

with open(src, 'r', encoding='utf-8') as f:
    data = f.read()

idx = data.index('printer_remaining_time')
msg_start = data.index("message: '", idx)

i = msg_start + len("message: '")
while i < len(data):
    if data[i] == "'":
        if i+1 < len(data) and data[i+1] == "'":
            i += 2
            continue
        else:
            end_quote = i
            break
    i += 1

old_template = data[msg_start:end_quote+1]
print(f'Old template: {len(old_template)} chars')

new_template = """message: '{% set a1mini = states(''sensor.a1mini_0300aa5a1600497_remaining_time'')
        %} {% set p2s = states(''sensor.p2s_22e8bj5a2401765_remaining_time'')
        %} {% set a1mini_status = states(''sensor.a1mini_0300aa5a1600497_print_status'')
        %} {% set p2s_status = states(''sensor.p2s_22e8bj5a2401765_print_status'')
        %} {% set now = now() %}
        %} {% set ns = namespace(a1mini_hours=0, a1mini_mins=0, p2s_hours=0, p2s_mins=0)
        %} {% if a1mini not in [''unknown'', ''unavailable'', ''''] and a1mini_status != ''failed''
        %} {% set ns.a1mini_hours = a1mini | float(default=0)
        %} {% set ns.a1mini_mins = ((ns.a1mini_hours - ns.a1mini_hours | int) * 60) | int
        %} {% endif %}
        %} {% if p2s not in [''unknown'', ''unavailable'', ''''] and p2s_status != ''failed''
        %} {% set ns.p2s_hours = p2s | float(default=0)
        %} {% set ns.p2s_mins = ((ns.p2s_hours - ns.p2s_hours | int) * 60) | int
        %} {% endif %}
        %} {% macro format_time(hours, mins)
        %} {% if hours > 0 and mins > 0 %} {{ hours }}小时{{ mins }}分钟 {% elif hours > 0 %} {{ hours }}小时 {% elif mins > 0 %} {{ mins }}分钟 {% else %} 即将完成 {% endif %}
        %} {% endmacro %}
        %} {% macro get_completion_time(remaining)
        %} {% if remaining not in [''unknown'', ''unavailable'', ''''] %} {{ (now + timedelta(hours=remaining | float(default=0))).strftime(''%H:%M'') }} {% else %} 未知 {% endif %}
        %} {% endmacro %}
        %} {% if a1mini not in [''unknown'', ''unavailable'', ''''] and a1mini | float(default=0) > 0 and a1mini_status != ''failed'' and p2s not in [''unknown'', ''unavailable'', ''''] and p2s | float(default=0) > 0 and p2s_status != ''failed''
        %} 打印中，小黑奴剩余{{ format_time(ns.a1mini_hours | int, ns.a1mini_mins) }}，预计{{ get_completion_time(a1mini) }}完成；大黑奴剩余{{ format_time(ns.p2s_hours | int, ns.p2s_mins) }}，预计{{ get_completion_time(p2s) }}完成。
        %} {% elif a1mini not in [''unknown'', ''unavailable'', ''''] and a1mini | float(default=0) > 0 and a1mini_status != ''failed''
        %} 打印中，小黑奴剩余{{ format_time(ns.a1mini_hours | int, ns.a1mini_mins) }}，预计{{ get_completion_time(a1mini) }}完成。
        %} {% elif p2s not in [''unknown'', ''unavailable'', ''''] and p2s | float(default=0) > 0 and p2s_status != ''failed''
        %} 打印中，大黑奴剩余{{ format_time(ns.p2s_hours | int, ns.p2s_mins) }}，预计{{ get_completion_time(p2s) }}完成。
        %} {% else %} 当前没有正在进行的打印任务。
        %} {% endif %}'"""

new_data = data.replace(old_template, new_template, 1)

assert 'a1mini_status' in new_data, 'FAIL: a1mini_status MISSING'
assert 'p2s_status' in new_data, 'FAIL: p2s_status MISSING'

with open(src, 'w', encoding='utf-8') as f:
    f.write(new_data)

print(f'Written: {len(new_data)} bytes')

# Verify YAML validity
with open(src, 'r', encoding='utf-8') as f:
    parsed = yaml.safe_load(f)
for item in parsed:
    if item.get('id') == 'printer_remaining_time':
        msg = item['actions'][0]['data']['message']
        assert 'a1mini_status' in msg, 'YAML: a1mini_status MISSING!'
        assert 'p2s_status' in msg, 'YAML: p2s_status MISSING!'
        assert "!= 'failed'" in msg, 'YAML: failed check MISSING!'
        print('YAML PARSE OK - all checks passed')
        break
print('ALL VERIFICATIONS PASSED')
