
bp = Blueprint('manual_verify', __name__)

            session.pop('manual_verify', None)
            return render_template('manual_verify.html', success=success)
        else:
            code = data['code'] if data else None
            error = '驗證碼錯誤，請重新輸入'
            return render_template('manual_verify.html', code=code, error=error)
    return render_template('manual_verify.html')
