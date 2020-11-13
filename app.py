import flask
from flask import request, jsonify
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import re
import pandas as pd
import contract as ct

UPLOAD_FOLDER = './uploads'
ALLOWED_EXTENSIONS = {'txt', }
pf_path = './preprocess/wc_pf.csv'
ff_path = './preprocess/wc_ff.csv'

app = flask.Flask(__name__)
# app.config["DEBUG"] = True
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def preprocess_file(file_path):
    msg_lists = list()
    i = 0
    with open(file_path, 'r') as f:
        for line in f.readlines():
            if re.match(r'./.*/.*, .*- .*:', line) is None:
                msg_lists[i - 1].append(line)
                continue
            else:
                r2 = line.replace(' - ', ',').replace(': ', ',').replace('\n', ' ')
                ftrs = r2.split(',')
                msg_lists.append(ftrs)
                i += 1

    with open(pf_path, 'w') as nf:
        nf.write('date,time,user,msg\n')
        for li in msg_lists:
            # print(len(li))
            f_str = "".join(li[3:]).strip().replace('\n', ' ').replace(',', ':')
            nr = f'{li[0]},{li[1].strip()},{li[2]},"{f_str}"\n'
            # print(nr)
            nf.write(nr)

    chat_data = pd.read_csv(pf_path,
                            skipinitialspace=True,
                            parse_dates={'datetime': [0, 1]})

    chat_data.to_csv(ff_path, index=False)


def get_chat_info():
    dict_tr = dict()
    chat_data = pd.read_csv(ff_path, parse_dates=['datetime'])
    c_time_format = lambda x: x.to_pydatetime().strftime('%d %B %Y, %I:%M %p')
    details = chat_data.describe()
    users = list(chat_data.user.unique())
    user_msgs = chat_data.user.value_counts()

    total_msgs = details.loc['count'][0]
    total_msgs_by = {str(user): str(user_msgs.loc[users].iloc[0]) for user in users}

    conv_start = c_time_format(details.loc['first'][0])
    conv_end = c_time_format(details.loc['last'][0])
    most_msgs_at = c_time_format(details.loc['top'][0])

    most_sent_msg = details.loc['top'][2]
    if most_sent_msg.lower() == '<media omitted>':
        most_sent_msg = 'Media Files'

    # BASIC INFORMATION
    dict_tr[ct.KEY_TOTALMSGS] = str(total_msgs)
    dict_tr[ct.KEY_USER1] = users[0]
    dict_tr[ct.KEY_USER2] = users[1]
    dict_tr[ct.KEY_TOTALMSGS_BY] = total_msgs_by
    dict_tr[ct.KEY_CONV_STARTED] = conv_start
    dict_tr[ct.KEY_CONV_ENDED] = conv_end
    dict_tr[ct.KEY_MOST_MSGS_AT] = most_msgs_at
    dict_tr[ct.KEY_MOST_SENT_MSG] = most_sent_msg

    # INTERMEDIATE INFORMATION
    chat_data['msg_len'] = chat_data['msg'].agg(len)
    longest_msgs = chat_data.groupby('user').msg_len.max()
    avg_msgs = chat_data.groupby('user').msg_len.mean()

    longest_msgs_by = {str(user): str(longest_msgs[user]) for user in users}
    avg_msgs_by = {str(user): f'{avg_msgs[user]:.1f} Chars' for user in users}
    avg_msg_len = f'{(avg_msgs[users[0]] + avg_msgs[users[1]]) / 2: .2f}'

    dict_tr[ct.KEY_LONGEST_MSG_BY] = longest_msgs_by
    dict_tr[ct.KEY_AVG_MSG_BY] = avg_msgs_by
    dict_tr[ct.KEY_AVG_MSG_LEN] = avg_msg_len

    # ADVANCE INFORMATION
    chat_data['day'] = chat_data['datetime'].dt.day_name()
    chat_data['week_num'] = chat_data['datetime'].dt.isocalendar().week
    chat_data['year'] = chat_data['datetime'].dt.year
    chat_data['time'] = chat_data.datetime - chat_data.datetime.dt.normalize()
    chat_data['time_spans'] = pd.cut(chat_data.time,
                                     bins=5,
                                     labels=['Late Night', 'Early Morning', 'Day Time', 'Evening', 'Night'])

    mostly_tm = chat_data.time_spans.value_counts(ascending=False)
    most_msgs_time = mostly_tm.index[0]
    most_time_msgs = mostly_tm.iloc[0]
    avg_msgs_day = chat_data.groupby(['year']).day.value_counts() / 34
    l_msg = chat_data.sort_values(by='msg_len', ascending=False).iloc[0]

    mta = f'{most_msgs_time}: {most_time_msgs}'
    avg_md = f'{avg_msgs_day.mean():.2f}'
    l_mat = f'{l_msg.day} {l_msg.time_spans} {l_msg.datetime.strftime("%I %p")}'

    dict_tr[ct.KEY_MOST_TALKED_AT] = mta
    dict_tr[ct.KEY_AVG_MSG_DAY] = avg_md
    dict_tr[ct.KEY_LONGEST_MSG_AT] = l_mat

    # MORE ADVANCE INFORMATION
    msgs_u_day = chat_data.groupby('user').day.value_counts()
    msgs_u_time = chat_data.groupby('user').time_spans.value_counts()

    mupd = {str(user): {str(idx): str(dy) for idx, dy in
                        zip(msgs_u_day.loc[user].index, msgs_u_day.loc[user])} for user in
            users}
    mupt = {str(user): {str(itx): str(tm) for itx, tm in
                        zip(msgs_u_time.loc[user].index, msgs_u_time.loc[user])} for user in
            users}

    dict_tr[ct.KEY_MSGS_DAY_BY] = mupd
    dict_tr[ct.KEY_MSGS_TIME_BY] = mupt
    return dict_tr


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'status': '400'})
        file = request.files['file']
        if file.filename == '':
            return jsonify({'status': '400'})
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename + str(datetime.now())) + '.txt'
            file.save(file_path)
            preprocess_file(file_path)

            res_data = get_chat_info()

            test_data = {
                ct.KEY_USER1: res_data[ct.KEY_USER1],
                ct.KEY_USER2: res_data[ct.KEY_USER2],
                ct.KEY_TOTALMSGS: res_data[ct.KEY_TOTALMSGS],
                ct.KEY_TOTALMSGS_BY: res_data[ct.KEY_TOTALMSGS_BY],
                ct.KEY_CONV_STARTED: res_data[ct.KEY_CONV_STARTED],
                ct.KEY_CONV_ENDED: res_data[ct.KEY_CONV_ENDED],
                ct.KEY_MOST_SENT_MSG: res_data[ct.KEY_MOST_SENT_MSG],
                ct.KEY_MOST_MSGS_AT: res_data[ct.KEY_MOST_MSGS_AT],
                ct.KEY_LONGEST_MSG_BY: res_data[ct.KEY_LONGEST_MSG_BY],
                ct.KEY_AVG_MSG_LEN: res_data[ct.KEY_AVG_MSG_LEN],
                ct.KEY_AVG_MSG_BY: res_data[ct.KEY_AVG_MSG_BY],
                ct.KEY_MOST_TALKED_AT: res_data[ct.KEY_MOST_TALKED_AT],
                ct.KEY_LONGEST_MSG_AT: res_data[ct.KEY_LONGEST_MSG_AT],
                ct.KEY_AVG_MSG_DAY: res_data[ct.KEY_AVG_MSG_DAY],
                ct.KEY_MSGS_DAY_BY: res_data[ct.KEY_MSGS_DAY_BY],
                ct.KEY_MSGS_TIME_BY: res_data[ct.KEY_MSGS_TIME_BY],
            }

            return jsonify(test_data)
    return 'Welcome to Web App'


if __name__ == '__main__':
    app.run()
