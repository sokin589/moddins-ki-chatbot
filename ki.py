from ollama import chat, ChatResponse
import re

def ask_deepseek(
    input_content,
    system_prompt="",
    model="llama3.1:8b",   
    deep_think=False,
    print_log=True
):
    response: ChatResponse = chat(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": input_content},
        ],
    )

    response_text = response["message"]["content"]

    if print_log:
        print(response_text)

    if not deep_think:
        return response_text, ""

    think_texts = re.findall(r"<think>(.*?)</think>", response_text, flags=re.DOTALL)
    think_texts = "\n\n".join(think_texts).strip()

    clean_response = re.sub(r"<think>.*?</think>", "", response_text, flags=re.DOTALL).strip()

    return clean_response, think_texts
