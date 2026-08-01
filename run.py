import os
from app import create_app, db
from app.models import User, Exam, Parameter, ReferenceValue, LayoutCell
from app.models import Order, Patient, Result, ParameterResult, PDFConfig
from flask_migrate import upgrade

app = create_app(os.environ.get('FLASK_ENV', 'development'))


@app.shell_context_processor
def make_shell_context():
    return dict(
        db=db,
        User=User,
        Exam=Exam,
        Parameter=Parameter,
        ReferenceValue=ReferenceValue,
        LayoutCell=LayoutCell,
        Order=Order,
        Patient=Patient,
        Result=Result,
        ParameterResult=ParameterResult,
        PDFConfig=PDFConfig,
    )


if __name__ == '__main__':
    app.run()
