from flask import Flask, render_template, request, make_response, jsonify
import base64
import os
from google.cloud import dialogflow_v2 as dialogflow_v2
import uuid
import json
from datetime import datetime
import pyodbc

file_name = "cred.json"


os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = file_name
app = Flask(__name__)

server = 'WIN-GEBOU8KV29T\\SQLEXPRESS'
database = 'projectpixcom'
conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};Trusted_Connection=yes'
db = pyodbc.connect(conn_str)


@app.route('/')
def serve_image():

  return render_template('index.html')


@app.route('/get_records', methods=['POST'])
def serve_ev_content():
    data = request.get_json()
    text_data=data.get('text')
    datetime_object = datetime.strptime(text_data, "%Y-%d-%m")
    formatted_date = datetime_object.strftime("%Y-%m-%d")
    print('date',formatted_date)
    cursor = db.cursor()
    
    cursor.execute("SELECT * FROM appointments WHERE appointment_date = ?", (formatted_date,))
    
    records = cursor.fetchall()
    
    contents = []
    for record in records:
        datetime_object = datetime.strptime(record[9], "%Y-%m-%d")
        formatted_date = datetime_object.strftime("%d-%m-%Y")
        contents.append({
                'date': formatted_date,
                'model': record[4],
                'name': record[1],
                'id': record[0],
                'email': record[2],
                'mobile': record[3],
                'mb': record[4],
                'expert': record[6],
                'room': record[8],
                'time': record[10],
                'message': record[7]
        })
    
    print("contents", contents)
    
    cursor.close()
    return render_template('event_content.html', contents=contents)


@app.route('/edit', methods=['POST'])
def edit_app():
  data = request.get_json()
  id = data.get('text')
  try:
    
    cursor = db.cursor()
    cursor.execute("SELECT * FROM appointments WHERE appointment_id =?", (id,))
    record = cursor.fetchone()

    if record:
      sql_time_str = str(record[10]).split('.')[0]  # Convert SQL time object to string
      print(sql_time_str)
      input_time = datetime.strptime(sql_time_str, "%H:%M:%S")  # Parse the time string
      formatted_time = input_time.strftime("%H:%M")
      
      result = {
                'date': record[9],
                'model': record[4],
                'name': record[1],
                'id': record[0],
                'email': record[2],
                'mobile': record[3],
                'mb': record[4],
                'expert': record[6],
                'room': record[8],
                'time':formatted_time ,
                'message': record[7]
      }
      return render_template('edit.html', data=result)
    else:
      return render_template('not_found.html'), 404
  except Exception as e:
    return render_template('error.html', error=str(e)), 500


@app.route('/delete', methods=['POST'])
def delete_app():
  data = request.get_json()
  appointment_id = data.get('text')
  try:
    cursor = db.cursor()
    cursor.execute("DELETE FROM appointments WHERE appointment_id = ?", (appointment_id,))
    db.commit()

    if cursor.rowcount > 0:
      return jsonify({"message": "Deleted Sucessfully"}), 200
    else:
      return jsonify({"message": "Failed to Delete Appointment"}), 200
  except Exception as e:
    print(e)
    response_data = {'message': "Failed to Delete Appointment"}
    return jsonify(response_data), 500


@app.route('/spotreveal')
def spot_reveal():
  id_param = request.args.get('id')
  try:
    cursor = db.cursor()
    
    cursor.execute("SELECT * FROM appointments WHERE appointment_id = ?", (id_param,))
    
    record = cursor.fetchone()
    
    if record:
      
      result = {
                'model': record[4],
                'name': record[1],
                'id': record[0],
                'email': record[2],
                'mobile': record[3],
                'mb': record[4],
                'expert': record[6],
                'room': record[8],
                'message': record[7]
      }
      return render_template('spot_reveal.html', content=result)
    else:
      return render_template('not_found.html'), 404
  except Exception as e:
    return render_template('error.html', error=str(e)), 500


@app.route('/dialog', methods=['POST'])
def receive_text_data():
  data = request.get_json()
  text_data = data.get('text')
  response = send_text_to_dialogflow(text_data)
  intent_name = response.query_result.intent.display_name
  fullfilment_text = response.query_result.fulfillment_text

  if intent_name == "date-picker":
    timestamp_str = response.query_result.parameters['date-time']
    if isinstance(timestamp_str, str) and timestamp_str != "":
      timestamp = datetime.fromisoformat(timestamp_str)
      extracted_date = timestamp.date()
      extracted_month = timestamp.month
      extracted_year = timestamp.year
      extracted_date = timestamp.day
      return jsonify({
          "intent_name": intent_name,
          "cdate": extracted_date,
          "cmonth": extracted_month,
          "cyear": extracted_year
      })
    else:
      return jsonify({
          "intent_name": "Default Fallback Intent",
          "fullfilment_text": "Invalid date format"
      })
  elif intent_name == "select-app" or intent_name == "edit-app" or intent_name == "delete-app":
    rec_num_ordinal = response.query_result.parameters['ordinal']
    rec_num_number = response.query_result.parameters['number']
    rec_num_number1 = response.query_result.parameters['num']
    if rec_num_ordinal:
      rec_num = rec_num_ordinal
    elif rec_num_number:
      rec_num = rec_num_number
    elif rec_num_number1:
      rec_num = rec_num_number1
    return jsonify({
        "intent_name": intent_name,
        "fullfilment_text": fullfilment_text,
        "rec_num": rec_num
    })
  elif intent_name == "month-selector":
    date_period_list = response.query_result.parameters['date-period']

    if date_period_list:
      # Taking the first date-period from the list
      date_period = date_period_list[0]

      # Extract start and end dates from the date period
      start_date_string = date_period.get('startDate', '')
      end_date_string = date_period.get('endDate', '')

      # Parse start and end dates into datetime objects
      start_date = datetime.fromisoformat(start_date_string)

      # Extract month and year from the start date
      month_num = start_date.month - 1
      year = start_date.year

      return jsonify({
          "intent_name": intent_name,
          "fullfilment_text": fullfilment_text,
          "month_num": month_num,
          "year": year
      })
    else:
      return jsonify({
          "intent_name": "Default Fallback Intent",
          "fullfilment_text": "provide month and year"
      })
  elif intent_name == "show-det":
    app_num = response.query_result.parameters['number-integer']
    if (app_num == ''):
      return jsonify({
          "intent_name": "Default Fallback Intent",
          "fullfilment_text": "provide appointment number"
      })
    else:
      return jsonify({
          "intent_name": intent_name,
          "fullfilment_text": fullfilment_text,
          "app_num": app_num
      })
  return jsonify({
      "intent_name": intent_name,
      "fullfilment_text": fullfilment_text
  })


@app.route('/save_app', methods=['POST'])
def save_app():
    try:
        data = request.get_json()
        cursor = db.cursor()
        name = data.get('name')
        email = data.get('email')
        mobile = data.get('mobile')
        mb = data.get('mb')
        date = data.get('datepicker')
        time = data.get('timepicker')
        model = data.get('model')
        expert = data.get('expert')
        room = data.get('room')
        message = data.get('message')
      
        sql = """
            INSERT INTO appointments (name, email, mobile, mb, model, expert, room, appointment_date, appointment_time, message, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        print('date',date)
        data = {
            'name': name,
            'email': email,
            'mobile': mobile,
            'mb': mb,
            'model': model,
            'expert': expert,
            'room': room,
            'appointment_date': date,
            'appointment_time': time,
            'message': message,
            'status': 'not delivered'
        }
        
        cursor.execute(sql, list(data.values()))

        db.commit()

        response_data = {'message': 'Appointment saved successfully'}
        return jsonify(response_data), 200
    except ValueError as ve:
        print("ValueError:", ve)
        response_data = {'message': "Invalid date format"}
        return jsonify(response_data), 400
    except Exception as e:
        print("Error:", e)
        response_data = {'message': "Failed to Save Appointment"}
        return jsonify(response_data), 500

@app.route('/update_app', methods=['POST'])
def update_app():
  try:
    data = request.get_json()

    # Handle the data as needed
    id = data.get('id')
    name = data.get('name')
    email = data.get('email')
    mobile = data.get('mobile')
    mb = data.get('mb')
    date = data.get('datepicker')
    time = data.get('timepicker')
    model = data.get('model')
    expert = data.get('expert')
    room = data.get('room')
    message = data.get('message')
    input_date = datetime.strptime(date, "%Y-%m-%d")
    cursor=db.cursor()
    # Format the date as dd-mm-yyyy
    sql_query = """
    UPDATE appointments
    SET name = ?,
        email = ?,
        mobile = ?,
        mb = ?,
        model = ?,
        expert = ?,
        room = ?,
        message = ?
    WHERE appointment_id = ?
    """
    cursor.execute(sql_query, (name, email, mobile, mb, model, expert, room,  message, id))

    db.commit()

    cursor.close()
    return {'message': 'Appointment updated successfully'}, 200
  except Exception as e:
    print(e)
    response_data = {'message': "Failed to update Appointment"}
    return jsonify(response_data), 500


def send_text_to_dialogflow(text):
  project_id = "ai-bot-qftk"

  # Generate a random session ID
  session_id = str(uuid.uuid4())

  session_client = dialogflow_v2.SessionsClient()
  session = session_client.session_path(project_id, session_id)

  text_input = dialogflow_v2.TextInput(text=text, language_code="en-US")
  query_input = dialogflow_v2.QueryInput(text=text_input)

  response = session_client.detect_intent(session=session,
                                          query_input=query_input)
  return response


if __name__ == "__main__":
  app.run(debug=False,host="0.0.0.0")

