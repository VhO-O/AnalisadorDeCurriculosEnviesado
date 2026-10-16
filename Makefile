ifeq ($(OS),Windows_NT)
	VENV = .venv
	PYTHON = $(VENV)/Scripts/python.exe
	PIP = $(VENV)/Scripts/pip.exe
	RM = rmdir /s /q
else	
	VENV = .venv
	PYTHON = $(VENV)/bin/python
	PIP = $(VENV)/bin/pip
	RM = rm -rf
endif

.PHONY: run setup clean

setup: 
ifeq ($(OS), Windows_NT)
	if not exist $(VENV) python -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
else
	if [ ! -d $(VENV) ]; then python -m venv $(VENV); fi
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
endif

run: setup
ifeq ($(OS), Windows_NT)
	$(VENV)/Scripts/streamlit.exe run streamlit_chatbot.py
else
	$(VENV)/bin/streamlit run streamlit_chatbot.py
endif

clean:
ifeq ($(OS), Windows_NT)
	if exist $(VENV) $(RM) $(VENV)
	pip cache purge
else
	if [ -d $(VENV) ]; then $(RM) $(VENV); fi
	pip cache purge
endif