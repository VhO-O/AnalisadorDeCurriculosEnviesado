VENV = .venv
PYTHON = $(VENV)/Scripts/python.exe
PIP = $(VENV)/Scripts/pip.exe

.PHONY: run setup clean

setup: 
	if not exist $(VENV) python -m venv $(VENV)
	$(PIP) install --upgrade pip
	if exist requirements.txt $(PIP) install -r requirements.txt

run: setup 
	$(VENV)/Scripts/streamlit.exe run streamlit_chatbot.py

clean:
	if exist $(VENV) rmdir /s /q $(VENV)