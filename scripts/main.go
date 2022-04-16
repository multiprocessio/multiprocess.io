package main

import (
	"encoding/json"
	"log"
	"net/http"
)

func test(rw http.ResponseWriter, req *http.Request) {
	decoder := json.NewDecoder(req.Body)
	var t []map[string]any
	err := decoder.Decode(&t)
	if err != nil {
		panic(err)
	}

	enc := json.NewEncoder(rw)
	err = enc.Encode(map[string]any{
		"status":        "ok",
		"new_documents": len(t),
	})
	if err != nil {
		panic(err)
	}
}

func main() {
	http.HandleFunc("/_docs", test)
	log.Fatal(http.ListenAndServe(":8081", nil))
}
